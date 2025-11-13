# scripts/server/services/azure_clients.py
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubProducerClient

_blob = None
_eh = None

def get_blob_service(account_name, account_key):
    global _blob
    if _blob: return _blob
    _blob = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=account_key,
    )
    return _blob

def get_eh_producer(conn_str, hub_name):
    global _eh
    if _eh: return _eh
    _eh = EventHubProducerClient.from_connection_string(
        conn_str=conn_str, eventhub_name=hub_name
    )
    return _eh
