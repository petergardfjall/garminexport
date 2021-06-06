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
import logging

from garminexport.garminclient import GarminClient

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
    parser.add_argument(
        "--domain", metavar="com", type=str,
        help="Top level domain of your Garmin Connect website. Default: com.",
        default="com")

    args = parser.parse_args()
    print(args)

    if not args.password:
        args.password = getpass.getpass("Enter password: ")
        
    client = GarminClient(args.username, args.password, domain=args.domain)
    client.connect()

    print("client object ready for use.")
