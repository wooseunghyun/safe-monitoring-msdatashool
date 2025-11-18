import logging
import os
from azure.storage.blob import BlobServiceClient


def upload_blob_from_memory(data_bytes, blob_name):
    try:
        # 🔥 디버깅용 출력
        print("DEBUG_BLOB_CONNECTION_STRING =", os.getenv("BLOB_CONNECTION_STRING"))
        print("DEBUG_BLOB_CONTAINER_NAME =", os.getenv("BLOB_CONTAINER_NAME"))

        connect_str = os.getenv("BLOB_CONNECTION_STRING")
        container_name = os.getenv("BLOB_CONTAINER_NAME")

        if not connect_str:
            logging.error("❌ Blob 연결 문자열이 비어 있습니다! (BLOB_CONNECTION_STRING 없음)")
            return

        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        blob_client.upload_blob(data_bytes, overwrite=True)
        logging.info(f"✔ Blob 업로드 성공: {blob_name}")

    except Exception as e:
        logging.error(f"❌ Blob 업로드 실패: {e}")
