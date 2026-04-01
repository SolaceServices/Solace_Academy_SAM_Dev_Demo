#!/usr/bin/env node
/**
 * mcp_postgres_rw.js — Read-write MCP server for PostgreSQL.
 *
 * The standard @modelcontextprotocol/server-postgres wraps every query in
 * BEGIN TRANSACTION READ ONLY, which rejects UPDATE and INSERT statements.
 * This server uses a normal read-write transaction so agents can both query
 * and modify data.
 *
 * This is also a minimal example of a custom MCP server — when an existing
 * server doesn't do what you need, you write your own using the MCP SDK.
 *
 * Usage:
 *   node ./mcp_postgres_rw.js <connection-string>
 *
 * Requires (already in 300-Agents/sam/node_modules via mcp-server-postgres):
 *   @modelcontextprotocol/sdk
 *   pg
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import pg from "pg";

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("Usage: node mcp_postgres_rw.js <connection-string>");
  process.exit(1);
}

const databaseUrl = args[0];
const resourceBaseUrl = new URL(databaseUrl);
resourceBaseUrl.protocol = "postgres:";
resourceBaseUrl.password = "";

const pool = new pg.Pool({ connectionString: databaseUrl });

const server = new Server(
  { name: "mcp-postgres-rw", version: "1.0.0" },
  { capabilities: { resources: {}, tools: {} } }
);

const SCHEMA_PATH = "schema";

// ── Resources: expose table schemas for context ────────────────────────────

server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const client = await pool.connect();
  try {
    const result = await client.query(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    );
    return {
      resources: result.rows.map((row) => ({
        uri: new URL(`${row.table_name}/${SCHEMA_PATH}`, resourceBaseUrl).href,
        mimeType: "application/json",
        name: `"${row.table_name}" database schema`,
      })),
    };
  } finally {
    client.release();
  }
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const resourceUrl = new URL(request.params.uri);
  const pathComponents = resourceUrl.pathname.split("/");
  const schema = pathComponents.pop();
  const tableName = pathComponents.pop();
  if (schema !== SCHEMA_PATH) {
    throw new Error("Invalid resource URI");
  }
  const client = await pool.connect();
  try {
    const result = await client.query(
      "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1",
      [tableName]
    );
    return {
      contents: [
        {
          uri: request.params.uri,
          mimeType: "application/json",
          text: JSON.stringify(result.rows, null, 2),
        },
      ],
    };
  } finally {
    client.release();
  }
});

// ── Tool: query (read-write) ───────────────────────────────────────────────

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "query",
      description: "Run a SQL query against the database (SELECT, UPDATE, INSERT, DELETE)",
      inputSchema: {
        type: "object",
        properties: {
          sql: { type: "string", description: "SQL statement to execute" },
        },
        required: ["sql"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "query") {
    const sql = request.params.arguments?.sql;
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      const result = await client.query(sql);
      await client.query("COMMIT");
      return {
        content: [
          { type: "text", text: JSON.stringify(result.rows ?? [], null, 2) },
        ],
        isError: false,
      };
    } catch (error) {
      await client.query("ROLLBACK").catch(() => {});
      throw error;
    } finally {
      client.release();
    }
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});

// ── Start ──────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
