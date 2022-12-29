from atlassian import Confluence
import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument("--username", help="username", required=True)
parser.add_argument("--password", help="passowrd", required=True)
parser.add_argument("--confluence",help="conflence source and confidential")
parser.add_argument("--page_id",help="conflence page id for attachument")
parser.add_argument("--output",help="output file folder")


args = parser.parse_args()
username = args.username
password = args.password
page_id = args.page_id
server_url = args.confluence
confluence = Confluence(server_url,username,token=password,verify_ssl=False)
attachments_container  = confluence.get_attachments_from_content(page_id)
attachments = attachments_container['results']
for attachment in attachments:
        fname = args.output + "/" + attachment['title']
        download_link = attachment['_links']['download']
        r = confluence.get(download_link, not_json_response=True)
        with open(fname, "wb") as f:
            f.write(r)
