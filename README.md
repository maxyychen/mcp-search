# SearXNG + MCP Bridge Docker Setup

This repository contains a Docker Compose setup that runs SearXNG (privacy-respecting metasearch engine) alongside the SearXNG MCP Bridge server.

## Services

### SearXNG
- **Port**: 8888
- **Description**: Privacy-respecting metasearch engine
- **Web Interface**: http://localhost:8888
- **Configuration**: `./searxng/config/settings.yml`
- **Data**: `./searxng/data/`

### SearXNG MCP Bridge
- **Port**: 8081
- **Description**: Model Context Protocol (MCP) bridge to SearXNG
- **API Endpoint**: http://localhost:8081/mcp
- **Transport**: HTTP mode
- **Health Check**: http://localhost:8081/healthz

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Start Services

```bash
docker-compose up -d
```

### Check Status

```bash
docker-compose ps
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f searxng
docker-compose logs -f searxng-mcp-bridge
```

### Stop Services

```bash
docker-compose down
```

## Testing

### Test SearXNG
Open in browser:
```
http://localhost:8888
```

### Test MCP Bridge

**Health Check:**
```bash
curl http://localhost:8081/healthz
```

**List Tools:**
```bash
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**Perform Search:**
```bash
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"search",
      "arguments":{"query":"docker containers"}
    }
  }'
```

## Configuration

### SearXNG Configuration
Edit `./searxng/config/settings.yml` to customize SearXNG settings:
- Search engines
- UI preferences
- Privacy settings
- Rate limiting

### MCP Bridge Environment Variables
Modify `docker-compose.yml` to change:
- `TRANSPORT`: `http` or `stdio` (default: `http`)
- `PORT`: HTTP server port (default: `8081`)
- `HOST`: Bind address (default: `0.0.0.0`)
- `SEARXNG_INSTANCE_URL`: SearXNG URL (default: `http://searxng:8080`)
- `CORS_ORIGIN`: Allowed CORS origins
- `MCP_HTTP_BEARER`: Optional bearer token for authentication

## Architecture

```
        ┌─────────────────┐
        │   User/Client   │
        └────────┬────────┘
                 │
         ┌───────┴───────┐
         │               │
         ▼               ▼
   Port 8888       Port 8081
  (Web UI)        (MCP API)
         │               │
         ▼               ▼
┌──────────────┐   ┌──────────────────┐
│   SearXNG    │◄──│  MCP Bridge      │
│   (Search)   │   │  (API Layer)     │
└──────────────┘   └──────────────────┘
         │                 │
         └─────────────────┘
        searxng-network
        (Internal: searxng:8080)
```

## Network

Both services communicate over the internal `searxng-network` bridge network:
- SearXNG is accessible internally as `http://searxng:8080`
- MCP Bridge connects to SearXNG using the internal hostname
- External access via exposed ports 8888 and 8081

## Volumes

- `./searxng/config` → `/etc/searxng` - Configuration files
- `./searxng/data` → `/var/cache/searxng` - Cache and data

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Port conflicts
If ports 8888 or 8081 are in use, edit `docker-compose.yml`:
```yaml
ports:
  - "9999:8080"  # Change 8888 to 9999
```

### MCP Bridge can't connect to SearXNG
Ensure both services are on the same network:
```bash
docker network inspect mcp_search_searxng-network
```

### Permission issues with volumes
```bash
# Fix permissions
chmod -R 755 ./searxng/config
chmod -R 755 ./searxng/data
```

## Development

### Rebuild MCP Bridge
```bash
docker-compose build searxng-mcp-bridge
docker-compose up -d searxng-mcp-bridge
```

### Access Container Shell
```bash
# SearXNG
docker exec -it searxng sh

# MCP Bridge
docker exec -it searxng-mcp-bridge sh
```

## References

- [SearXNG Documentation](https://docs.searxng.org/)
- [SearXNG GitHub](https://github.com/searxng/searxng)
- [SearXNG MCP Bridge](https://github.com/nitish-raj/searxng-mcp-bridge)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

See individual component licenses:
- SearXNG: AGPLv3
- SearXNG MCP Bridge: MIT
