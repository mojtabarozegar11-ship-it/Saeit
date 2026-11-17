#!/usr/bin/env python3
"""Read-only owner/staging Passenger and media-scope evidence; NEVER a backup.

No live Passenger worker attachment, request, SQL, uploads/file contents, DDL,
remote network calls, subprocesses, archive writes, or production modifications.
Outputs only finite enums, counts and boolean facts. A staging WSGI source hint
is NOT evidence of currently serving worker identity or production DB parity.
"""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import pwd
import stat
import sys

OWNER='zomorod2'
HOME=Path('/home/zomorod2')
STAGING=HOME/'Saeit-staging'
WEBROOT=HOME/'mojplaywin.com'
ENTRY=WEBROOT/'passenger_wsgi.py'
MAX_ENTRY=32768
MAX_DIRECT=128
CANDIDATES={
 'staging_media':STAGING/'media',
 'staging_uploads':STAGING/'uploads',
 'webroot_media':WEBROOT/'media',
 'webroot_uploads':WEBROOT/'uploads',
 'public_html_media':HOME/'public_html'/'media',
 'public_html_uploads':HOME/'public_html'/'uploads',
}
PREFIX='FACTORY_C169_PASSENGER_MEDIA_SCOPE_READONLY='


def owned_regular(path:Path,uid:int,directory:bool)->bool:
    try: s=path.lstat()
    except OSError:return False
    if s.st_uid!=uid or s.st_mode & 0o022:return False
    if directory:return stat.S_ISDIR(s.st_mode)
    return stat.S_ISREG(s.st_mode) and s.st_nlink==1


def ancestors_safe(path:Path,uid:int)->bool:
    if not (HOME==path or HOME in path.parents):return False
    curr=path
    while True:
        if not owned_regular(curr,uid,True):return False
        if curr==HOME:return True
        curr=curr.parent


def wsgi_signals(source:bytes)->dict:
    out={'parsed':False,'staging_literal':False,'application_declared':False,
         'django_settings_literal':False,'wsgi_loader_symbol_present':False}
    if type(source) is not bytes or not 1<=len(source)<=MAX_ENTRY:
        return out
    # Bound AST input nesting before parsing even maliciously deep expressions.
    level=0
    for c in source:
        if c in (40,91,123):
            level+=1
            if level>128:return out
        elif c in (41,93,125):level=max(0,level-1)
    try: tree=ast.parse(source.decode('utf-8'))
    except (SyntaxError,UnicodeDecodeError,RecursionError,MemoryError,ValueError):return out
    values=[x.value for x in ast.walk(tree) if isinstance(x,ast.Constant) and type(x.value) is str]
    out['parsed']=True
    out['staging_literal']=str(STAGING) in values
    out['django_settings_literal']='config.settings' in values
    out['wsgi_loader_symbol_present']=any(isinstance(x,ast.Name) and x.id=='get_wsgi_application' for x in ast.walk(tree))
    out['application_declared']=any(
        isinstance(n,(ast.Assign,ast.AnnAssign)) and any(isinstance(t,ast.Name) and t.id=='application'
               for t in (n.targets if isinstance(n,ast.Assign) else [n.target]))
        for n in tree.body)
    return out


def storage_flags(config)->dict:
    state={'database_backend':'unknown','database_name_configured':False,
           'media_root_state':'unknown','file_backend':'unknown',
           'configured_media_root_owner_safe':False,
           'app_media_complete':False,'production_worker_db_identity_verified':False}
    try:
        d=config.DATABASES.get('default',{})
        if type(d) is dict:
            state['database_backend']='mysql' if d.get('ENGINE')=='django.db.backends.mysql' else 'other'
            state['database_name_configured']=bool(d.get('NAME'))
        s=getattr(config,'STORAGES',None)
        back=s.get('default',{}).get('BACKEND') if type(s) is dict and type(s.get('default')) is dict else None
        state['file_backend']=('filesystem' if back=='django.core.files.storage.FileSystemStorage'
                               else 'other_configured' if type(back) is str and bool(back) else 'unknown')
        root=getattr(config,'MEDIA_ROOT',None)
        if root in (None,'','.'):state['media_root_state']='not_configured'
        elif not isinstance(root,(str,Path)):
            state['media_root_state']='invalid_type'
        elif not Path(root).is_absolute():
            state['media_root_state']='relative_unverified'
        elif HOME not in Path(root).parents:
            state['media_root_state']='outside_owner_home'
        else:
            state['media_root_state']='configured_under_home_unverified'
            # Ancestor and configured path checked separately by caller.
    except (AttributeError,TypeError,ValueError,RuntimeError,KeyError):
        pass
    return state


def fixed_candidate_status(path:Path,uid:int)->dict:
    result={'state':'unknown','bounded_scan_complete':False,'regular_files':0,
            'subdirectories':0,'symlinks':0,'direct_bytes':0,
            'recursive_scope_proven':False,'file_content_read':False}
    try:
        if HOME not in path.parents:
            result['state']='outside_fixed_home';return result
        if not path.exists() and not path.is_symlink():
            result['state']='missing';return result
        if not ancestors_safe(path,uid):
            result['state']='unsafe_or_unavailable';return result
        result['state']='owner_safe_directory'
        n=0
        with os.scandir(path) as entries:
            for entry in entries:
                n+=1
                if n>MAX_DIRECT:
                    result['state']='entry_limit_exceeded';return result
                s=entry.stat(follow_symlinks=False)
                if s.st_uid!=uid or s.st_mode&0o022:
                    result['state']='unsafe_child_found';return result
                if stat.S_ISLNK(s.st_mode):result['symlinks']+=1
                elif stat.S_ISDIR(s.st_mode):result['subdirectories']+=1
                elif stat.S_ISREG(s.st_mode):
                    result['regular_files']+=1
                    result['direct_bytes']+=max(0,s.st_size)
                else:
                    result['state']='special_child_found';return result
        result['bounded_scan_complete']=True
    except OSError:
        result['state']='unavailable'
    return result


def report()->dict:
    out={'schema':'factory.cpanel.passenger-media-scope.readonly.c169.v1',
         'read_only':True,'owner_verified':False,'staging_safe':False,
         'passenger_source_safe':False,'passenger_ast':wsgi_signals(b''),
         'settings_loaded_in_process':False,'configured':storage_flags(None),
         'fixed_candidate_metadata':{k:fixed_candidate_status_stub() for k in CANDIDATES},
         'customer_rows_or_upload_contents_read':False,'mysql_connection_opened':False,
         'passenger_runtime_worker_identified':False,'full_app_media_backup_scope_proven':False,
         'cloud_quota_verified':False,'current_backup_created':False,
         'production_release_authorized':False,'new_cost_incurred':False}
    try:
        uid=os.geteuid()
        if pwd.getpwuid(uid).pw_name!=OWNER:return out
        out['owner_verified']=True
        if not all(owned_regular(x,uid,True) for x in (HOME,STAGING,STAGING/'config',WEBROOT)):
            return out
        if not owned_regular(STAGING/'config'/'settings.py',uid,False):return out
        out['staging_safe']=True
        if owned_regular(ENTRY,uid,False):
            with ENTRY.open('rb') as f:
                source=f.read(MAX_ENTRY+1)
            if 0<len(source)<=MAX_ENTRY:
                out['passenger_source_safe']=True
                out['passenger_ast']=wsgi_signals(source)
        out['fixed_candidate_metadata']={k:fixed_candidate_status(p,uid) for k,p in CANDIDATES.items()}
        os.chdir(STAGING)
        if str(STAGING) not in sys.path:sys.path.insert(0,str(STAGING))
        os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
        from django.conf import settings
        _=settings.DATABASES
        out['configured']=storage_flags(settings)
        out['settings_loaded_in_process']=True
        # Even with valid filesystem flags the actual Passenger worker is
        # neither executed nor attached: this fact MUST remain false.
    except (OSError,ImportError,AttributeError,TypeError,ValueError,RuntimeError,KeyError):
        pass
    return out


def fixed_candidate_status_stub():
    return {'state':'not_attempted','bounded_scan_complete':False,'regular_files':0,
            'subdirectories':0,'symlinks':0,'direct_bytes':0,
            'recursive_scope_proven':False,'file_content_read':False}

if __name__=='__main__':
    print(PREFIX+json.dumps(report(),sort_keys=True,separators=(',',':')))
