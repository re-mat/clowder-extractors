import os
from boxsdk import Client, CCGAuth
from boxsdk.exception import BoxAPIException


class BoxHandler:
    def __init__(self):
        """
        Initializes the Box client using credentials from environment variables.
        Expects:
        - BOX_CLIENT_ID
        - BOX_CLIENT_SECRET
        - BOX_ENTERPRISE_ID (for CCG authentication with a Service Account)
          OR
        - BOX_USER_ID (for CCG authentication as a specific user, remove enterprise_id in this case)
        """
        self.client_id = os.getenv("BOX_CLIENT_ID", "rhtgt26vyj3fxa92c450iibqckolijfi")
        self.client_secret = os.getenv("BOX_TOKEN")
        self.enterprise_id = os.getenv("BOX_ENTERPRISE_ID", "83165")

        if not self.client_secret:
            raise ValueError("Missing environment variable: BOX_TOKEN")

        auth = CCGAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            enterprise_id=self.enterprise_id,
        )
        try:
            self.client = Client(auth)
            print("Successfully authenticated to Box")
        except BoxAPIException as e:
            print(f"Box API Authentication Error: {e.message} (Status: {e.status})")
            if hasattr(e, "context_info") and e.context_info:
                print(f"Context Info: {e.context_info}")
            raise  # Re-raise the exception after printing details

    def _resolve_shared_link_to_folder_id(self, shared_link: str) -> str:
        """
        Resolves a Box shared link to its numeric folder ID.
        """
        try:
            shared_item = self.client.get_shared_item(shared_link)
            if shared_item.type != "folder":
                raise ValueError(
                    f"The shared link '{shared_link}' does not point to a folder (points to a {shared_item.type})."
                )
            # return the folder id
            return shared_item.id
        except BoxAPIException as e:
            print(f"Error resolving shared link '{shared_link}': {e.message}")
            raise

    def download_file_by_name_from_shared_link(
        self, shared_link: str, file_name: str, temp_file_path: str
    ):
        """
        Downloads a file by its name from a folder specified by a shared link.

        Args:
            shared_link (str): The shareable URL of the Box folder.
            file_name (str): The name of the file to download from the folder.
            temp_file_path (str): The local path (including filename) where the file will be downloaded.
        """
        try:
            folder_id = self._resolve_shared_link_to_folder_id(shared_link)
            items = self.client.folder(folder_id).get_items()
            file_id_to_download = None
            for item in items:
                if item.type == "file" and item.name == file_name:
                    file_id_to_download = item.id
                    break

            if not file_id_to_download:
                raise FileNotFoundError(
                    f"Datasheet File '{file_name}' not found in Box folder (ID: {folder_id}) resolved from link '{shared_link}'."
                )

            with open(temp_file_path, "wb") as output_file:
                self.client.file(file_id_to_download).download_to(output_file)
            print(f"File '{file_name}' downloaded successfully to {temp_file_path}")

        except FileNotFoundError:  # Re-raise FileNotFoundError specifically
            raise
        except BoxAPIException as e:
            print(
                f"Box API error during file download operation: {e.message} (Status: {e.status})"
            )
            if hasattr(e, "context_info") and e.context_info:
                print(f"Context Info: {e.context_info}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred while downloading from box: {e}")
            raise
