from typing import Dict, List, Tuple

from meraki_snapshot.client import MerakiClient
from meraki_snapshot.storage import SnapshotWriter


class BackupSummary:
    def __init__(self, root: str, networks: List[Dict[str, str]]):
        self.root = root
        self.networks = networks


class BackupManager:
    def __init__(self, client: MerakiClient, output_dir: str):
        self.client = client
        self.output_dir = output_dir

    def snapshot(self) -> BackupSummary:
        org = self.client.get_organization()
        networks = self.client.list_networks()
        admins = self.client.list_org_admins()
        templates = self.client.list_config_templates()

        writer = SnapshotWriter(self.output_dir, self.client.org_id)
        network_summaries: List[Dict[str, str]] = []

        for net in networks:
            net_id = net["id"]
            product_types = net.get("productTypes", [])
            devices = self.client.list_devices(net_id)
            config = self.client.collect_network_config(net_id, product_types)
            writer.write_network(net, devices, config)
            network_summaries.append(
                {
                    "id": net_id,
                    "name": net.get("name", net_id),
                    "productTypes": ",".join(product_types),
                    "folder": writer.network_paths(net.get("name", net_id))[0].split(writer.root + "/")[-1],
                }
            )

        writer.write_index(
            {
                "created_at": writer.snap_ts,
                "organization": org,
                "admins": admins,
                "config_templates": templates,
                "networks": network_summaries,
                "network_count": len(network_summaries),
            }
        )

        return BackupSummary(writer.root, network_summaries)
