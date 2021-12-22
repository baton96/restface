import itertools
import uuid

import tinydb

from .JSONStorage import JSONStorage


class FileStorage(JSONStorage):
    def __init__(self, storage_path: str = None, uuid_id: bool = False):
        super().__init__(storage_path, uuid_id)
        if storage_path:
            self.db = tinydb.TinyDB(storage_path)
        else:
            self.db = tinydb.TinyDB(storage=tinydb.storages.MemoryStorage)

    def get_with_id(self, table_name: str, item_id: int) -> dict:
        table = self.get_table(table_name)
        return table.get(doc_id=item_id) or {}

    def get_without_id(self, table_name: str, where_params: list, meta_params: dict):
        table = self.get_table(table_name)
        items = [
            item for item in table.all() if all(
                self.fulfill_cond(item, param)
                for param in where_params
            )
        ]

        # Sorting, keep None-s and put them on the beginning of results
        order_by = meta_params['order_by']
        order_key = lambda item: tuple(
            [
                ((value := item.get(order_by_arg.lstrip('-'))) is not None, value)
                for order_by_arg in order_by
            ] + [item['id']]
        )

        desc = meta_params['desc']
        items = sorted(items, key=order_key, reverse=desc)

        offset = meta_params['_offset']
        limit = meta_params['_limit'] or len(items) - offset
        return items[offset: offset + limit]

    def post(self, table_name: str, data: dict):
        table = self.get_table(table_name)
        item_id = data.get('id')
        if not item_id:
            item_ids = {item['id'] for item in table.all()}
            if self.primary_type == int:
                item_id = max(item_ids or {0}) + 1
            elif self.primary_type == str:
                generator = (str(uuid.uuid4()) for _ in itertools.count())
                for item_id in generator:
                    if item_id not in item_ids:
                        break
            data['id'] = item_id
        return table.upsert(tinydb.table.Document(data, doc_id=item_id))[0]

    def delete(self, table_name: str, item_id: int = None) -> bool:
        if item_id:
            table = self.get_table(table_name)
            try:
                table.remove(doc_ids=[item_id])
                return True
            except KeyError:
                return False
        else:
            existed = table_name in self.db.tables()
            self.db.drop_table(table_name)
            return existed

    def all(self):
        return {
            table_name: {
                row.get('id'): row
                for row in self.get_table(table_name).all()
            } for table_name in self.db.tables()
        }

    def reset(self):
        self.db.drop_tables()

    def get_table(self, table_name):
        table = self.db.table(table_name)
        table.document_id_class = self.primary_type
        return table
