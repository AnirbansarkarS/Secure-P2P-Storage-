#!/usr/bin/env python3
"""
Generate cryptographic keys for P2P nodes
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.shared.crypto import CryptoUtils
import click


@click.command()
@click.option('--output-dir', default='./keys', help='Directory to save keys')
@click.option('--peer-id', help='Optional peer ID (generated if not provided)')
@click.option('--format', type=click.Choice(['pem', 'json']), default='pem', help='Output format')
def generate_keys(output_dir, peer_id, format):
    """Generate ECC key pair for a P2P node"""
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate peer ID if not provided
    if not peer_id:
        import uuid
        peer_id = str(uuid.uuid4())
    
    click.echo(f"Generating keys for peer: {peer_id}")
    
    # Generate key pair
    crypto = CryptoUtils()
    private_key, public_key = crypto.generate_key_pair()
    
    if format == 'pem':
        # Save as PEM files
        private_key_path = output_path / f"{peer_id}_private.pem"
        public_key_path = output_path / f"{peer_id}_public.pem"
        
        with open(private_key_path, 'wb') as f:
            f.write(private_key)
        
        with open(public_key_path, 'wb') as f:
            f.write(public_key)
        
        click.echo(f"✓ Private key saved to: {private_key_path}")
        click.echo(f"✓ Public key saved to: {public_key_path}")
        
    elif format == 'json':
        # Save as JSON
        keys_data = {
            'peer_id': peer_id,
            'private_key': private_key.decode('utf-8'),
            'public_key': public_key.decode('utf-8')
        }
        
        json_path = output_path / f"{peer_id}_keys.json"
        with open(json_path, 'w') as f:
            json.dump(keys_data, f, indent=2)
        
        click.echo(f"✓ Keys saved to: {json_path}")
    
    click.echo(f"\n⚠️  Keep your private key secure!")
    click.echo(f"Peer ID: {peer_id}")


@click.command()
@click.argument('key_file', type=click.Path(exists=True))
def show_key_info(key_file):
    """Display information about a key file"""
    
    key_path = Path(key_file)
    
    if key_path.suffix == '.json':
        with open(key_path, 'r') as f:
            data = json.load(f)
        
        click.echo(f"Peer ID: {data['peer_id']}")
        click.echo(f"Has private key: {'private_key' in data}")
        click.echo(f"Has public key: {'public_key' in data}")
    
    elif key_path.suffix == '.pem':
        with open(key_path, 'rb') as f:
            key_data = f.read()
        
        if b'PRIVATE' in key_data:
            click.echo("Type: Private Key")
        elif b'PUBLIC' in key_data:
            click.echo("Type: Public Key")
        
        click.echo(f"Size: {len(key_data)} bytes")


@click.group()
def cli():
    """Cryptographic key management for Secure P2P Storage"""
    pass


cli.add_command(generate_keys, name='generate')
cli.add_command(show_key_info, name='info')


if __name__ == '__main__':
    cli()
