import consul
import json
from typing import Optional
from src.namespace_config import NamespaceConfig


class ConsulNamespaceStore:
    KEY_PREFIX = "zanzibar/namespaces"

    def __init__(self, host: str = 'localhost', port: int = 8500):
        self.consul = consul.Consul(host=host, port=port)

    def _namespace_key(self, namespace: str) -> str:
        return f"{self.KEY_PREFIX}/{namespace}"

    def save_namespace(self, config: NamespaceConfig):
        key = self._namespace_key(config.namespace)
        config_data = config.to_dict()
        self.consul.kv.put(key, json.dumps(config_data))

    def get_namespace(self, namespace: str) -> Optional[NamespaceConfig]:
        key = self._namespace_key(namespace)
        _, data = self.consul.kv.get(key)

        if data is None:
            return None

        config_data = json.loads(data['Value'].decode())
        return NamespaceConfig.from_dict(config_data)
