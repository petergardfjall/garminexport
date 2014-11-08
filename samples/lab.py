#! /usr/bin/env python
"""
Script intended for Garmin Connect API experimenting in ipython.
un as:
  ipython -i samples/lab.py -- --password=<password> <username>

and use the client object (or client.session) to interact with
Garmin Connect.
"""

import argparse
import getpass
from garminexport.garminclient import GarminClient
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":   
    parser = argparse.ArgumentParser()
    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")

    args = parser.parse_args()
    print(args)

    if not args.password:
        args.password = getpass.getpass("Enter password: ")
        
    client = GarminClient(args.username, args.password)
    client.connect()

    print("client object ready for use.")
