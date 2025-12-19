import click
import asyncio
from pathlib import Path
import json
from typing import Optional
from ..p2p.node import P2PNode
from ..shared.config import Config

@click.group()
def cli():
    """Secure P2P Storage Client"""
    pass

@cli.command()
@click.option('--coordinator', default="http://localhost:8000", help='Coordinator URL')
@click.option('--port', default=9000, help='Port for P2P communication')
@click.option('--data-dir', default='./p2p_data', help='Data directory')
def start(coordinator: str, port: int, data_dir: str):
    """Start a P2P node"""
    click.echo(f"Starting P2P node on port {port}...")
    
    # Create node
    node = P2PNode(coordinator_url=coordinator)
    
    # Start node
    asyncio.run(node.start(port))
    
    # Keep running
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        click.echo("\nShutting down...")

@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--coordinator', default="http://localhost:8000", help='Coordinator URL')
@click.option('--password', prompt=True, hide_input=True, help='Encryption password')
def upload(file_path: str, coordinator: str, password: str):
    """Upload a file to the P2P network"""
    async def _upload():
        node = P2PNode(coordinator_url=coordinator)
        await node.start(9001)  # Temporary port for client
        
        file_hash = await node.store_file(file_path, password)
        click.echo(f"File uploaded successfully!")
        click.echo(f"File hash: {file_hash}")
        click.echo(f"Password: {password} (SAVE THIS SECURELY!)")
        
        # Generate recovery info
        recovery_info = {
            "file_hash": file_hash,
            "coordinator": coordinator,
            "encryption_scheme": "AES-256-GCM"
        }
        
        recovery_file = f"{Path(file_path).stem}_recovery.json"
        with open(recovery_file, 'w') as f:
            json.dump(recovery_info, f, indent=2)
        
        click.echo(f"Recovery info saved to: {recovery_file}")
    
    asyncio.run(_upload())

@cli.command()
@click.argument('file_hash')
@click.option('--coordinator', default="http://localhost:8000", help='Coordinator URL')
@click.option('--output', type=click.Path(), help='Output file path')
@click.option('--password', prompt=True, hide_input=True, help='Encryption password')
def download(file_hash: str, coordinator: str, output: Optional[str], password: str):
    """Download a file from the P2P network"""
    async def _download():
        node = P2PNode(coordinator_url=coordinator)
        await node.start(9002)  # Temporary port for client
        
        file_data = await node.retrieve_file(file_hash, password)
        
        if not output:
            output_path = f"downloaded_{file_hash[:8]}"
        else:
            output_path = output
        
        with open(output_path, 'wb') as f:
            f.write(file_data)
        
        click.echo(f"File downloaded to: {output_path}")
    
    asyncio.run(_download())

@cli.command()
@click.argument('file_hash')
@click.option('--coordinator', default="http://localhost:8000", help='Coordinator URL')
def info(file_hash: str, coordinator: str):
    """Get information about a stored file"""
    import aiohttp
    import asyncio
    
    async def _get_info():
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                f"{coordinator}/file/{file_hash}/locations"
            )
            
            if response.status == 200:
                data = await response.json()
                click.echo(json.dumps(data, indent=2))
            else:
                click.echo(f"File not found: {file_hash}")
    
    asyncio.run(_get_info())

@cli.command()
@click.option('--coordinator', default="http://localhost:8000", help='Coordinator URL')
@click.option('--min-reputation', default=0.0, help='Minimum reputation')
def peers(coordinator: str, min_reputation: float):
    """List available peers"""
    import aiohttp
    import asyncio
    
    async def _list_peers():
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                f"{coordinator}/peers",
                params={"min_reputation": min_reputation}
            )
            
            if response.status == 200:
                peers = await response.json()
                for peer in peers:
                    click.echo(f"{peer['peer_id']} - {peer['ip_address']}:{peer['port']} "
                             f"(Rep: {peer['reputation']}, Storage: {peer['available_storage']}GB)")
            else:
                click.echo("Failed to get peers list")
    
    asyncio.run(_list_peers())

if __name__ == "__main__":
    cli()