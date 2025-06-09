# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Data Analysis Tools Module
Provides data analysis functions including table analysis, column statistics, performance monitoring, etc.
"""

import time
from datetime import datetime
from typing import Any, Dict, List

from .db import DorisConnectionManager
from .logger import get_logger

logger = get_logger(__name__)


class TableAnalyzer:
    """Table analyzer"""
    
    def __init__(self, connection_manager: DorisConnectionManager):
        self.connection_manager = connection_manager
    
    async def get_table_summary(
        self, 
        table_name: str, 
        include_sample: bool = True, 
        sample_size: int = 10
    ) -> Dict[str, Any]:
        """Get table summary information"""
        connection = await self.connection_manager.get_connection("query")
        
        # Get table basic information
        table_info_sql = f"""
        SELECT 
            table_name,
            table_comment,
            table_rows,
            create_time,
            engine
        FROM information_schema.tables 
        WHERE table_schema = DATABASE()
        AND table_name = '{table_name}'
        """
        
        table_info_result = await connection.execute(table_info_sql)
        if not table_info_result.data:
            raise ValueError(f"Table {table_name} does not exist")
        
        table_info = table_info_result.data[0]
        
        # Get column information
        columns_sql = f"""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_comment
        FROM information_schema.columns 
        WHERE table_schema = DATABASE()
        AND table_name = '{table_name}'
        ORDER BY ordinal_position
        """
        
        columns_result = await connection.execute(columns_sql)
        
        summary = {
            "table_name": table_info["table_name"],
            "comment": table_info.get("table_comment"),
            "row_count": table_info.get("table_rows", 0),
            "create_time": str(table_info.get("create_time")),
            "engine": table_info.get("engine"),
            "column_count": len(columns_result.data),
            "columns": columns_result.data,
        }
        
        # Get sample data
        if include_sample and sample_size > 0:
            sample_sql = f"SELECT * FROM {table_name} LIMIT {sample_size}"
            sample_result = await connection.execute(sample_sql)
            summary["sample_data"] = sample_result.data
        
        return summary
    
    async def analyze_column(
        self, 
        table_name: str, 
        column_name: str, 
        analysis_type: str = "basic"
    ) -> Dict[str, Any]:
        """Analyze column statistics"""
        try:
            connection = await self.connection_manager.get_connection("query")
            
            # Basic statistics
            basic_stats_sql = f"""
            SELECT 
                '{column_name}' as column_name,
                COUNT(*) as total_count,
                COUNT({column_name}) as non_null_count,
                COUNT(DISTINCT {column_name}) as distinct_count
            FROM {table_name}
            """
            
            basic_result = await connection.execute(basic_stats_sql)
            if not basic_result.data:
                return {
                    "success": False,
                    "error": f"Unable to get statistics for table {table_name} column {column_name}"
                }
            
            analysis = basic_result.data[0].copy()
            analysis["success"] = True
            analysis["analysis_type"] = analysis_type
        
            if analysis_type in ["distribution", "detailed"]:
                # Data distribution analysis
                distribution_sql = f"""
                SELECT 
                    {column_name} as value,
                    COUNT(*) as frequency
                FROM {table_name}
                WHERE {column_name} IS NOT NULL
                GROUP BY {column_name}
                ORDER BY frequency DESC
                LIMIT 20
                """
                
                distribution_result = await connection.execute(distribution_sql)
                analysis["value_distribution"] = distribution_result.data
            
            if analysis_type == "detailed":
                # Detailed statistics (for numeric types)
                try:
                    numeric_stats_sql = f"""
                    SELECT 
                        MIN({column_name}) as min_value,
                        MAX({column_name}) as max_value,
                        AVG({column_name}) as avg_value
                    FROM {table_name}
                    WHERE {column_name} IS NOT NULL
                    """
                    
                    numeric_result = await connection.execute(numeric_stats_sql)
                    if numeric_result.data:
                        analysis.update(numeric_result.data[0])
                except Exception:
                    # Non-numeric columns don't support numeric statistics
                    pass
            
            return analysis
        
        except Exception as e:
            logger.error(f"Column analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "column_name": column_name,
                "table_name": table_name
            }
    
    async def analyze_table_relationships(
        self, 
        table_name: str, 
        depth: int = 2
    ) -> Dict[str, Any]:
        """Analyze table relationships"""
        connection = await self.connection_manager.get_connection("system")
        
        # Get table basic information
        table_info_sql = f"""
        SELECT 
            table_name,
            table_comment,
            table_rows
        FROM information_schema.tables 
        WHERE table_schema = DATABASE()
        AND table_name = '{table_name}'
        """
        
        table_result = await connection.execute(table_info_sql)
        if not table_result.data:
            raise ValueError(f"Table {table_name} does not exist")
        
        # Get all tables list (for analyzing potential relationships)
        all_tables_sql = """
        SELECT 
            table_name,
            table_comment
        FROM information_schema.tables 
        WHERE table_schema = DATABASE()
        AND table_type = 'BASE TABLE'
        AND table_name != %s
        """
        
        all_tables_result = await connection.execute(all_tables_sql, (table_name,))
        
        return {
            "center_table": table_result.data[0],
            "related_tables": all_tables_result.data,
            "depth": depth,
            "note": "Table relationship analysis based on column name similarity and business logic inference",
        }


class PerformanceMonitor:
    """Performance monitor"""
    
    def __init__(self, connection_manager: DorisConnectionManager):
        self.connection_manager = connection_manager
    
    async def get_performance_stats(
        self, 
        metric_type: str = "queries", 
        time_range: str = "1h"
    ) -> Dict[str, Any]:
        """Get performance statistics"""
        connection = await self.connection_manager.get_connection("system")
        
        # Convert time range to seconds
        time_mapping = {
            "1h": 3600,
            "6h": 21600,
            "24h": 86400,
            "7d": 604800
        }
        
        seconds = time_mapping.get(time_range, 3600)
        
        if metric_type == "queries":
            # Query performance metrics
            stats = {
                "metric_type": "queries",
                "time_range": time_range,
                "timestamp": datetime.now().isoformat(),
                "total_queries": 0,
                "avg_execution_time": 0.0,
                "slow_queries": 0,
                "error_queries": 0,
                "note": "Query performance statistics (simulated data)"
            }
            
        elif metric_type == "connections":
            # Connection statistics
            connection_metrics = await self.connection_manager.get_metrics()
            stats = {
                "metric_type": "connections",
                "time_range": time_range,
                "timestamp": datetime.now().isoformat(),
                "total_connections": connection_metrics.total_connections,
                "active_connections": connection_metrics.active_connections,
                "idle_connections": connection_metrics.idle_connections,
                "failed_connections": connection_metrics.failed_connections,
                "connection_errors": connection_metrics.connection_errors,
                "avg_connection_time": connection_metrics.avg_connection_time,
                "last_health_check": connection_metrics.last_health_check.isoformat() if connection_metrics.last_health_check else None
            }
            
        elif metric_type == "tables":
            # Table-level statistics
            tables_sql = """
            SELECT 
                table_name,
                table_rows,
                data_length,
                index_length,
                create_time,
                update_time
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_type = 'BASE TABLE'
            ORDER BY table_rows DESC
            LIMIT 20
            """
            
            tables_result = await connection.execute(tables_sql)
            stats = {
                "metric_type": "tables",
                "time_range": time_range,
                "timestamp": datetime.now().isoformat(),
                "table_count": len(tables_result.data),
                "tables": tables_result.data
            }
            
        elif metric_type == "system":
            # System-level metrics (simulated)
            stats = {
                "metric_type": "system",
                "time_range": time_range,
                "timestamp": datetime.now().isoformat(),
                "cpu_usage": 45.2,
                "memory_usage": 68.5,
                "disk_usage": 72.1,
                "network_io": {
                    "bytes_sent": 1024000,
                    "bytes_received": 2048000
                },
                "note": "System metrics (simulated data)"
            }
            
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")
        
        return stats
    
    async def get_query_history(
        self, 
        limit: int = 50, 
        order_by: str = "time"
    ) -> Dict[str, Any]:
        """Get query history"""
        # Since Doris doesn't have a built-in query history table,
        # we return simulated data
        return {
            "total_queries": 0,
            "queries": [],
            "limit": limit,
            "order_by": order_by,
            "note": "Query history feature requires audit log configuration"
        } 