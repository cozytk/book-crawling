"""Verified product discovery, independent of short-lived rating caches.

Only metadata is stored. Every use still fetches and validates a fresh detail
page. A title query must first establish the same local author; explicit ISBNs
never substitute a cached product. Native audits and verified server search
cards can supply discoveries without embedding book IDs in crawler code.
"""
import asyncio
import re
import time
import math
import unicodedata
from urllib.parse import urlsplit

VERSION=1
TTL=30*86400


def normalize(query):
    value=unicodedata.normalize('NFKC',query).casefold()
    value=re.sub(r'아래서(?=$|\s*[(\[])','아래',value)
    return ''.join(c for c in value if c.isalnum())


def validation_title(title):
    # Store the full observed title, but edition marketing is optional on the
    # same ASIN's detail heading. Volume markers are retained.
    if re.search(r'\b(?:vol(?:ume)?\.?|part|band|book)\s+(?:\d+|[IVX]+)\b',title,re.I):
        return title
    primary=re.split(r'\s[-–—]\s|[:：]',title,maxsplit=1)[0]
    return re.sub(r'\([^)]*(?:edition|classics|international|paperback|hardcover|kindle)[^)]*\)','',primary,flags=re.I).strip()


def validate(value,query,platform='amazon'):
    if not isinstance(value,dict) or value.get('version')!=VERSION or value.get('platform')!=platform:
        return None
    expiry=value.get('expires_at')
    if not isinstance(expiry,(int,float)) or not math.isfinite(expiry) or expiry<=time.time():
        return None
    if not isinstance(value.get('query'),str) or normalize(value['query'])!=normalize(query):
        return None
    try:
        url=urlsplit(value.get('url',''))
    except (ValueError,TypeError):
        return None
    if platform!='amazon' or url.scheme!='https' or url.netloc!='www.amazon.com' or url.query or url.fragment:
        return None
    if not re.fullmatch(r'/dp/[A-Z0-9]{10}',url.path):
        return None
    if any(not isinstance(value.get(k),str) or not value[k].strip() or len(value[k])>500
           for k in ['title','source_author','local_author']):
        return None
    if value.get('provenance') not in {'aside_book_search','server_verified_search_card'}:
        return None
    alternates=value.get('alternates',[])
    if not isinstance(alternates,list) or len(alternates)>2:
        return None
    for alternate in alternates:
        if not isinstance(alternate,dict):
            return None
        if alternate.get('source_author')!=value['source_author']:
            return None
        child={**value,**alternate,'alternates':[]}
        if not validate(child,query,platform):
            return None
    return value


async def read(store,query,platform='amazon'):
    if not store or not hasattr(store,'source_identity_cached'):
        return None
    try:
        value=await asyncio.wait_for(asyncio.to_thread(store.source_identity_cached,query,platform),1.5)
        return validate(value,query,platform)
    except Exception:
        return None


async def write(store,value):
    if not store or not hasattr(store,'cache_source_identity') or not validate(value,value.get('query',''),value.get('platform')):
        return
    try:
        await asyncio.wait_for(asyncio.to_thread(store.cache_source_identity,value['query'],value['platform'],value),2)
    except Exception:
        pass
