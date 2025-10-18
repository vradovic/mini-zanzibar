import plyvel

class ACLTuple:
    def __init__(self, object_id, relation, user):
        self.object_id = object_id
        self.relation = relation
        self.user = user

    @classmethod
    def from_string(cls, s):
        # Primer: "doc:readme#viewer@user:alice"
        try:
            obj_rel, user = s.split('@')
            object_id, relation = obj_rel.split('#')
            return cls(object_id, relation, user)
        except Exception:
            raise ValueError("Invalid ACL tuple format")

    def to_string(self):
        return f"{self.object_id}#{self.relation}@{self.user}"

class ACLDB:
    def __init__(self, db_path='leveldb_data'):
        self.db = plyvel.DB(db_path, create_if_missing=True)

    def add_acl(self, acl_tuple: ACLTuple):
        key = acl_tuple.to_string().encode()
        self.db.put(key, b'1')

    def remove_acl(self, acl_tuple: ACLTuple):
        key = acl_tuple.to_string().encode()
        self.db.delete(key)

    def check_acl(self, acl_tuple: ACLTuple):
        key = acl_tuple.to_string().encode()
        return self.db.get(key) is not None

    def close(self):
        self.db.close()
