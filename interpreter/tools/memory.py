"""
Memory Tool for Open Interpreter.
This tool allows the agent to store and recall memories from short-term and long-term memory.
"""

import asyncio
import datetime
import json
import os
import time
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union

import asyncpg
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult

# Constants for memory configuration
DEFAULT_SHORT_TERM_CAPACITY = 100  # Number of items in short-term memory
SHORT_TERM_DECAY_HOURS = 24  # Short term memories start decaying after this time
MEMORY_HALF_LIFE_DAYS = 30  # Memories lose half their importance after this many days
RECENCY_WEIGHT = 0.7  # Weight given to recency vs frequency in memory ranking
FREQUENCY_WEIGHT = 0.3  # Weight given to frequency vs recency in memory ranking


class MemoryStorage:
    """
    Handles the storage and retrieval of memories in both short-term and long-term stores.
    Short-term memory is kept in memory for quick access.
    Long-term memory is stored in PostgreSQL for persistence.
    """

    def __init__(self):
        self.short_term_memory = []  # List of recent memories for quick access
        self.db_pool = None  # PostgreSQL connection pool
        self.is_initialized = False

    async def initialize(self):
        """Initialize the memory storage, including database connection."""
        if self.is_initialized:
            return

        try:
            # Create PostgreSQL connection pool
            self.db_pool = await asyncpg.create_pool(
                user="postgres",
                password="Bfoster15!",
                database="postgres",
                host="localhost",
                port=5432
            )

            # Create tables if they don't exist
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS memories (
                        id SERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 1
                    )
                ''')

                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS memory_tags (
                        id SERIAL PRIMARY KEY,
                        memory_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
                        tag TEXT NOT NULL
                    )
                ''')

                # Create indexes for faster querying
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_tags_tag ON memory_tags(tag)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_tags_memory_id ON memory_tags(memory_id)')

            self.is_initialized = True
            return ToolResult(output="Memory storage initialized successfully.")

        except Exception as e:
            return ToolResult(error=f"Failed to initialize memory storage: {str(e)}")

    async def store(self, content: str, tags: List[str] = None, metadata: Dict = None) -> ToolResult:
        """
        Store a memory in both short-term and long-term memory.

        Args:
            content: The content of the memory to store
            tags: List of tags/keywords for categorizing the memory
            metadata: Additional structured data about the memory

        Returns:
            ToolResult with the outcome of the storage operation
        """
        if not self.is_initialized:
            await self.initialize()

        try:
            # Prepare memory object
            timestamp = datetime.datetime.now()
            memory = {
                "content": content,
                "tags": tags or [],
                "metadata": metadata or {},
                "created_at": timestamp,
                "last_accessed": timestamp,
                "access_count": 1
            }

            # Store in short-term memory (with capacity limit)
            self.short_term_memory.append(memory)
            if len(self.short_term_memory) > DEFAULT_SHORT_TERM_CAPACITY:
                # Remove oldest memory if capacity exceeded
                self.short_term_memory.pop(0)

            # Store in long-term memory (PostgreSQL)
            async with self.db_pool.acquire() as conn:
                # Insert memory
                memory_id = await conn.fetchval('''
                    INSERT INTO memories (content, metadata, created_at, last_accessed, access_count)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                ''', content, json.dumps(metadata or {}), timestamp, timestamp, 1)

                # Insert tags
                if tags:
                    await conn.executemany('''
                        INSERT INTO memory_tags (memory_id, tag)
                        VALUES ($1, $2)
                    ''', [(memory_id, tag) for tag in tags])

            return ToolResult(output=f"Memory stored successfully with {len(tags or [])} tags.")

        except Exception as e:
            return ToolResult(error=f"Failed to store memory: {str(e)}")

    async def recall(self, query: str = None, tags: List[str] = None,
                     limit: int = 5, use_long_term: bool = True) -> ToolResult:
        """
        Recall memories based on query and/or tags.
        Checks short-term memory first, then long-term if requested.

        Args:
            query: Text to search for in memory content
            tags: Tags to filter memories
            limit: Maximum number of memories to return
            use_long_term: Whether to check long-term memory if not found in short-term

        Returns:
            ToolResult with the recalled memories
        """
        if not self.is_initialized:
            await self.initialize()

        try:
            results = []

            # First, check short-term memory
            short_term_results = self._search_short_term(query, tags)

            # If we found enough in short-term memory, just return those
            if len(short_term_results) >= limit:
                results = short_term_results[:limit]

            # Otherwise, also check long-term memory if requested
            elif use_long_term:
                # Get results from long-term memory
                long_term_results = await self._search_long_term(query, tags, limit - len(short_term_results))
                results = short_term_results + long_term_results
            else:
                results = short_term_results

            # Update access counts and last_accessed timestamp for retrieved memories
            memory_ids = [r.get("id") for r in results if r.get("id")]
            if memory_ids and self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute('''
                        UPDATE memories 
                        SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                        WHERE id = ANY($1)
                    ''', memory_ids)

            if not results:
                return ToolResult(output="No memories found matching the criteria.")

            # Format the results nicely
            formatted_results = []
            for i, result in enumerate(results, 1):
                memory_str = f"{i}. {result['content']}"
                if result.get("tags"):
                    memory_str += f" [Tags: {', '.join(result['tags'])}]"
                if result.get("score"):
                    memory_str += f" (Relevance: {result['score']:.2f})"
                formatted_results.append(memory_str)

            return ToolResult(output=f"Found {len(results)} memories:\n\n" + "\n\n".join(formatted_results))

        except Exception as e:
            return ToolResult(error=f"Failed to recall memories: {str(e)}")

    def _search_short_term(self, query: str = None, tags: List[str] = None) -> List[Dict]:
        """Search for memories in short-term memory."""
        if not self.short_term_memory:
            return []

        results = self.short_term_memory.copy()

        # Filter by query if provided
        if query:
            results = [m for m in results if query.lower()
                       in m["content"].lower()]

        # Filter by tags if provided
        if tags:
            results = [m for m in results if any(
                tag in m.get("tags", []) for tag in tags)]

        # Calculate memory importance based on recency and frequency
        now = datetime.datetime.now()
        for result in results:
            # Calculate recency score (newer is better)
            age_hours = (now - result["created_at"]).total_seconds() / 3600
            recency_score = 1.0 / (1.0 + age_hours / SHORT_TERM_DECAY_HOURS)

            # Calculate frequency score
            frequency_score = min(
                result["access_count"] / 10.0, 1.0)  # Cap at 1.0

            # Combined score
            result["score"] = (RECENCY_WEIGHT * recency_score) + \
                (FREQUENCY_WEIGHT * frequency_score)

        # Sort by score (highest first)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    async def _search_long_term(self, query: str = None, tags: List[str] = None, limit: int = 5) -> List[Dict]:
        """Search for memories in long-term memory (PostgreSQL)."""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                base_query = '''
                    SELECT m.id, m.content, m.metadata, m.created_at, m.last_accessed, m.access_count,
                           array_agg(mt.tag) as tags,
                           (
                               -- Calculate recency score
                               $1 * (1.0 / (1.0 + EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - m.last_accessed))/86400/$3)) +
                               -- Calculate frequency score
                               $2 * LEAST(m.access_count / 10.0, 1.0)
                           ) as score
                    FROM memories m
                    LEFT JOIN memory_tags mt ON m.id = mt.memory_id
                '''

                params = [RECENCY_WEIGHT, FREQUENCY_WEIGHT,
                          MEMORY_HALF_LIFE_DAYS]
                where_clauses = []

                # Add content search if query provided
                if query:
                    where_clauses.append(
                        "m.content ILIKE $" + str(len(params) + 1))
                    params.append(f"%{query}%")

                # Add tag filtering if tags provided
                if tags:
                    where_clauses.append(
                        "mt.tag = ANY($" + str(len(params) + 1) + ")")
                    params.append(tags)

                # Complete the query
                if where_clauses:
                    base_query += " WHERE " + " AND ".join(where_clauses)

                # Group by, order by score, and limit
                base_query += '''
                    GROUP BY m.id, m.content, m.metadata, m.created_at, m.last_accessed, m.access_count
                    ORDER BY score DESC
                    LIMIT $''' + str(len(params) + 1)
                params.append(limit)

                # Execute query
                rows = await conn.fetch(base_query, *params)

                results = []
                for row in rows:
                    results.append({
                        "id": row["id"],
                        "content": row["content"],
                        "tags": row["tags"] or [],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                        "created_at": row["created_at"],
                        "last_accessed": row["last_accessed"],
                        "access_count": row["access_count"],
                        "score": row["score"]
                    })

                return results

        except Exception as e:
            print(f"Error searching long-term memory: {e}")
            return []

    async def forget(self, memory_id: int = None, older_than_days: int = None) -> ToolResult:
        """
        Remove memories from both short-term and long-term storage.

        Args:
            memory_id: Specific memory ID to forget
            older_than_days: Forget memories older than this many days

        Returns:
            ToolResult indicating what was forgotten
        """
        if not self.is_initialized:
            await self.initialize()

        try:
            count = 0

            # Handle forgetting by ID
            if memory_id:
                # Remove from short-term memory
                self.short_term_memory = [
                    m for m in self.short_term_memory if m.get("id") != memory_id]

                # Remove from long-term memory
                async with self.db_pool.acquire() as conn:
                    result = await conn.execute('DELETE FROM memories WHERE id = $1', memory_id)
                    # Parse count from DELETE X
                    count = int(result.split()[-1])

            # Handle forgetting by age
            elif older_than_days:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=older_than_days)

                # Remove from short-term memory
                old_count = len(self.short_term_memory)
                self.short_term_memory = [
                    m for m in self.short_term_memory if m["created_at"] > cutoff_date]
                count += old_count - len(self.short_term_memory)

                # Remove from long-term memory
                async with self.db_pool.acquire() as conn:
                    result = await conn.execute('DELETE FROM memories WHERE created_at < $1', cutoff_date)
                    # Parse count from DELETE X
                    count += int(result.split()[-1])

            return ToolResult(output=f"Forgot {count} memories.")

        except Exception as e:
            return ToolResult(error=f"Failed to forget memories: {str(e)}")

    async def summarize(self, tags: List[str] = None, days: int = 30) -> ToolResult:
        """
        Generate a summary of memories, optionally filtered by tags and time period.

        Args:
            tags: Only summarize memories with these tags
            days: Only summarize memories from the past X days

        Returns:
            ToolResult with the memory summary
        """
        if not self.is_initialized:
            await self.initialize()

        try:
            async with self.db_pool.acquire() as conn:
                base_query = '''
                    SELECT COUNT(*) as total_count,
                           MIN(created_at) as earliest,
                           MAX(created_at) as latest,
                           array_agg(DISTINCT tag) as all_tags
                    FROM memories m
                    LEFT JOIN memory_tags mt ON m.id = mt.memory_id
                    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '$1 days'
                '''

                params = [days]

                if tags:
                    base_query += " AND tag = ANY($2)"
                    params.append(tags)

                row = await conn.fetchrow(base_query, *params)

                if row["total_count"] == 0:
                    return ToolResult(output=f"No memories found in the past {days} days.")

                # Get most frequent tags
                tag_query = '''
                    SELECT tag, COUNT(*) as tag_count
                    FROM memory_tags mt
                    JOIN memories m ON mt.memory_id = m.id
                    WHERE m.created_at > CURRENT_TIMESTAMP - INTERVAL '$1 days'
                    GROUP BY tag
                    ORDER BY tag_count DESC
                    LIMIT 5
                '''

                top_tags = await conn.fetch(tag_query, days)

                # Format summary
                summary = f"Memory Summary (past {days} days):\n\n"
                summary += f"Total memories: {row['total_count']}\n"
                summary += f"Time span: {row['earliest'].strftime('%Y-%m-%d')} to {row['latest'].strftime('%Y-%m-%d')}\n"

                if top_tags:
                    summary += "\nTop tags:\n"
                    for tag_row in top_tags:
                        summary += f"- {tag_row['tag']} ({tag_row['tag_count']} memories)\n"

                return ToolResult(output=summary)

        except Exception as e:
            return ToolResult(error=f"Failed to summarize memories: {str(e)}")


# Singleton instance of memory storage
_memory_storage = MemoryStorage()


class MemoryTool(BaseAnthropicTool):
    """Tool for storing and recalling memories with short and long-term persistence."""

    name: ClassVar[Literal["memory"]] = "memory"
    api_type: ClassVar[Literal["function"]] = "function"

    async def __call__(self, action: str, content: str = None, query: str = None,
                       tags: List[str] = None, memory_id: int = None,
                       older_than_days: int = None, days: int = 30,
                       limit: int = 5, use_long_term: bool = True, **kwargs) -> ToolResult:
        """
        Execute memory operations for storing, recalling, and managing memories.

        Args:
            action: The memory action to perform (store, recall, forget, summarize)
            content: Content to store (for 'store' action)
            query: Text to search for (for 'recall' action)
            tags: Tags for categorizing or filtering memories
            memory_id: ID of a specific memory (for 'forget' action)
            older_than_days: Age threshold for forgetting (for 'forget' action)
            days: Time period in days (for 'summarize' action)
            limit: Maximum number of memories to return (for 'recall' action)
            use_long_term: Whether to check long-term memory (for 'recall' action)
        """
        print(f"Memory tool called with action: {action}, args: {kwargs}")

        # Initialize memory storage if needed
        if not _memory_storage.is_initialized:
            await _memory_storage.initialize()

        # Execute the requested action
        if action == "store" and content:
            return await _memory_storage.store(content, tags)

        elif action == "recall":
            return await _memory_storage.recall(query, tags, limit, use_long_term)

        elif action == "forget":
            return await _memory_storage.forget(memory_id, older_than_days)

        elif action == "summarize":
            return await _memory_storage.summarize(tags, days)

        else:
            return ToolResult(error=f"Invalid memory action: {action}. Valid actions are: store, recall, forget, summarize")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
            "function": {
                "name": self.name,
                "description": "Store and recall memories with human-like memory characteristics including decay, using both short-term and long-term memory storage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["store", "recall", "forget", "summarize"],
                            "description": "The memory operation to perform"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to store in memory (for 'store' action)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Text to search for in memories (for 'recall' action)"
                        },
                        "tags": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Tags/keywords for categorizing or filtering memories"
                        },
                        "memory_id": {
                            "type": "integer",
                            "description": "ID of a specific memory to forget (for 'forget' action)"
                        },
                        "older_than_days": {
                            "type": "integer",
                            "description": "Forget memories older than this many days (for 'forget' action)"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (for 'summarize' action)",
                            "default": 30
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of memories to return (for 'recall' action)",
                            "default": 5
                        },
                        "use_long_term": {
                            "type": "boolean",
                            "description": "Whether to check long-term memory if not found in short-term (for 'recall' action)",
                            "default": True
                        }
                    },
                    "required": ["action"],
                },
            },
        }
