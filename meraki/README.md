# Meraki dashboard automation

This folder houses the lightweight Meraki Dashboard automation toolkit:

- `lib/meraki_client.py` exposes a small Python client that wraps the v1 Meraki
  REST API and supports common CRUD workflows (networks and devices).
- `script/meraki/cli.py` offers a command-line interface built on top of the
  client. Supply credentials via CLI flags, environment variables, or a JSON
  config file to list, create, update, and delete networks as well as
  claim/remove devices.

## Example usage

```bash
# Execute directly
python script/meraki/cli.py list-networks

# Or run as a module (keeps imports tidy)
python -m script.meraki.cli list-networks

# Create a network that combines MX and MS products
python script/meraki/cli.py create-network --name "Lab" --product-types MX MS --tags lab sandbox

# Update the notes field on an existing network
python script/meraki/cli.py update-network N_1234 --set notes="Used for QA"
```

## Configuration file

Instead of exporting environment variables, create a JSON file at
`~/.config/meraki/config.json` (default location) with the following structure:

```json
{
  "api_key": "your_api_key",
  "org_id": "your_org_id"
}
```

Then run commands without extra flags:

```bash
python script/meraki/cli.py list-networks
```

You can point to a different config file via `--config /path/to/creds.json`. Any
value passed explicitly on the CLI still overrides config and env defaults.

The client relies on the `requests` library, which is bundled with most Python
environments. If it is missing, install it with `pip install requests`.

