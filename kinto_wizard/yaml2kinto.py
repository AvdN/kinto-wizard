from __future__ import print_function
from .logger import logger
from .kinto2yaml import introspect_server


def initialize_server(client, config, force=False):
    logger.debug("Converting YAML config into a server batch.")
    # 1. Introspect current server state.
    if not force:
        current_server_status = introspect_server(client)
    else:
        # We don't need to load it because we will override it nevertheless.
        current_server_status = {}
    # 2. For each bucket
    with client.batch() as batch:
        for bucket_id, bucket in config.items():
            bucket_exists = bucket_id in current_server_status
            bucket_data = bucket.get('data', {})
            bucket_permissions = bucket.get('permissions', {})
            bucket_groups = bucket.get('groups', {})
            bucket_collections = bucket.get('collections', {})

            if not bucket_exists:
                bucket_current_groups = {}
                bucket_current_collections = {}

                # Create the bucket if not present in the introspection
                batch.create_bucket(id=bucket_id,
                                    data=bucket_data,
                                    permissions=bucket_permissions,
                                    safe=(not force))
            else:
                bucket_current_groups = current_server_status[bucket_id]['groups']
                bucket_current_collections = current_server_status[bucket_id]['collections']

                # Patch the bucket if mandatory
                current_bucket = current_server_status[bucket_id]
                current_bucket_data = current_bucket.get('data', {})
                current_bucket_permissions = current_bucket.get('permissions', {})

                if (current_bucket_data != bucket_data or
                        current_bucket_permissions != bucket_permissions):
                    batch.patch_bucket(id=bucket_id,
                                       data=bucket_data,
                                       permissions=bucket_permissions)

            # 2.1 For each group, patch it if needed
            for group_id, group_info in bucket_groups.items():
                group_exists = bucket_exists and group_id in bucket_current_groups
                group_data = group_info.get('data', {})
                group_permissions = group_info.get('permissions', {})

                if not group_exists:
                    batch.create_group(id=group_id,
                                       bucket=bucket_id,
                                       data=group_data,
                                       permissions=group_permissions,
                                       safe=(not force))
                else:
                    current_group = bucket_current_groups[group_id]
                    current_group_data = current_group.get('data', {})
                    current_group_permissions = current_group.get('permissions', {})

                    if (current_group_data != group_data or
                            current_group_permissions != group_permissions):
                        batch.patch_group(id=group_id,
                                          bucket=bucket_id,
                                          data=group_data,
                                          permissions=group_permissions)

            # 2.2 For each collection patch it if mandatory
            for collection_id, collection in bucket_collections.items():
                collection_exists = bucket_exists and collection_id in bucket_current_collections
                collection_data = collection.get('data', {})
                collection_permissions = collection.get('permissions', {})

                if not collection_exists:
                    batch.create_collection(id=collection_id,
                                            bucket=bucket_id,
                                            data=collection_data,
                                            permissions=collection_permissions,
                                            safe=(not force))
                else:
                    current_collection = bucket_current_collections[collection_id]
                    current_collection_data = current_collection.get('data', {})
                    current_collection_permissions = current_collection.get('permissions', {})

                    if (current_collection_data != collection_data or
                            current_collection_permissions != collection_permissions):
                        batch.patch_collection(id=collection_id,
                                               bucket=bucket_id,
                                               data=collection_data,
                                               permissions=collection_permissions)

                # 2.2.1 For each collection, create its records.
                collection_records = collection.get('records', {})
                for record_id, record in collection_records.items():
                    record_exists = (collection_exists and
                                     record_id in current_collection['records'])
                    record_data = record.get('data', {})
                    record_permissions = record.get('permissions', None)

                    if not record_exists:
                        batch.create_record(id=record_id,
                                            bucket=bucket_id,
                                            collection=collection_id,
                                            data=record_data,
                                            permissions=record_permissions,
                                            safe=(not force))
                    else:
                        current_record = current_collection['records'][record_id]
                        current_record_data = current_record.get('data', {})
                        # XXX: we don't show permissions, until we have a way to fetch records
                        # in batch (see Kinto/kinto-http.py#145)
                        current_record_permissions = current_record.get('permissions', {})

                        if (current_record_data != record_data or
                                current_record_permissions != record_permissions):
                            batch.update_record(id=record_id,
                                                bucket=bucket_id,
                                                collection=collection_id,
                                                data=record_data,
                                                permissions=record_permissions)

        logger.debug('Sending batch:\n\n%s' % batch.session.requests)
    logger.info("Batch uploaded")
