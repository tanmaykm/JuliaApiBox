import boto.dynamodb.exceptions

from db.db_base import JBoxDB


class JBoxApiSpec(JBoxDB):
    NAME = 'jbox_apispec'
    TABLE = None

    def __init__(self, api_name, create=False):
        if self.table() is None:
            self.is_new = False
            self.item = None
            return
        
        try:
            self.item = self.table().get_item(hash_key=api_name)
            self.log_debug("got " + repr(self.item))
            self.is_new = False
        except boto.dynamodb.exceptions.DynamoDBKeyNotFoundError:
            if create:
                self.item = self.table().new_item(hash_key=api_name)
                self.is_new = True
            else:
                raise

    def _item_get(self, name, defval, noitemval):
        if self.item is not None:
            return self.item.get(name, defval)
        else:
            return noitemval

    def _item_set(self, name, val):
        if self.item is not None:
            self.item[name] = val

    def get_api_name(self):
        return self._item_get('api_name', None, None)

    def get_endpoint_in(self):
        return self._item_get('endpt_in', None, None)

    def get_endpoint_out(self):
        return self._item_get('endpt_out', None, None)

    def get_timeout_secs(self):
        return self._item_get('timeout_secs', 30, None)

    def get_methods(self):
        return self._item_get('methods', '', '').split(',')

    def get_publisher(self):
        return self._item_get('publisher', None, None)

    def get_image_name(self):
        return self._item_get('image_name', 'juliabox/juliaboxapi:latest', None)

    def get_cmd(self):
        return self._item_get('cmd', None, None)

    def set_methods(self, methods):
        self._item_set('methods', ','.join(methods))

    def set_timeout_secs(self, timeout_secs):
        self._item_set('timeout_secs', timeout_secs)

    def set_endpoint_in(self, endpt_in):
        self._item_set('endpt_in', endpt_in)

    def set_endpoint_out(self, endpt_out):
        self._item_set('endpt_out', endpt_out)

    def set_publisher(self, publisher):
        self._item_set('publisher', publisher)