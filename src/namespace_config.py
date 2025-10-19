from typing import Dict, List, Optional, Any


class NamespaceConfig:
    def __init__(self, namespace: str, relations: Dict[str, Any]):
        self.namespace = namespace
        self.relations = relations
        self._validate()

    def _validate(self):
        if not self.namespace:
            raise ValueError("Namespace cannot be empty")

        if not isinstance(self.relations, dict):
            raise ValueError("Relations must be a dictionary")

        for relation_name, relation_def in self.relations.items():
            if not isinstance(relation_def, dict):
                raise ValueError(
                    f"Relation '{relation_name}' definition must be a dictionary")

            if 'union' in relation_def:
                if not isinstance(relation_def['union'], list):
                    raise ValueError(
                        f"Union in relation '{relation_name}' must be a list")

                for union_item in relation_def['union']:
                    if not isinstance(union_item, dict):
                        raise ValueError(
                            f"Union item in '{relation_name}' must be a dictionary")

                    if 'this' not in union_item and 'computed_userset' not in union_item:
                        raise ValueError(
                            f"Union item in '{relation_name}' must have 'this' or 'computed_userset'"
                        )

                    if 'computed_userset' in union_item:
                        computed = union_item['computed_userset']
                        if 'relation' not in computed:
                            raise ValueError(
                                f"computed_userset in '{relation_name}' must have 'relation' field"
                            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'namespace': self.namespace,
            'relations': self.relations
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NamespaceConfig':
        return cls(
            namespace=data['namespace'],
            relations=data['relations']
        )

    def get_relation_definition(self, relation: str) -> Optional[Dict[str, Any]]:
        return self.relations.get(relation)

    def has_relation(self, relation: str) -> bool:
        return relation in self.relations

    def compute_inherited_relations(self, relation: str) -> List[str]:
        inherited = []
        visited = set()

        def traverse(rel: str):
            if rel in visited or rel not in self.relations:
                return

            visited.add(rel)
            inherited.append(rel)

            rel_def = self.relations[rel]

            # Check for union operations
            if 'union' in rel_def:
                for union_item in rel_def['union']:
                    if 'computed_userset' in union_item:
                        parent_rel = union_item['computed_userset']['relation']
                        traverse(parent_rel)

        traverse(relation)
        return inherited
