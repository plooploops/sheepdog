"""
Test upload entities (mostly data file handling and communication with
index service).
"""
import copy
import json
import re

import pytest

from test_endpoints import put_cgci_blgsp

from utils import assert_positive_response
from utils import assert_negative_response
from utils import assert_single_entity_from_response

# Python 2 and 3 compatible
try:
    from unittest.mock import MagicMock
    from unittest.mock import patch
except ImportError:
    from mock import MagicMock
    from mock import patch

from gdcdatamodel.models import SubmittedAlignedReads
from sheepdog.transactions.upload.sub_entities import FileUploadEntity
from sheepdog.test_settings import SUBMISSION
from sheepdog.utils import (
    generate_s3_url,
    set_indexd_state,
)
from tests.integration.submission.test_versioning import release_indexd_doc

PROGRAM = 'CGCI'
PROJECT = 'BLGSP'
BLGSP_PATH = '/v0/submission/{}/{}/'.format(PROGRAM, PROJECT)

# some default values for data file submissions
DEFAULT_FILE_HASH = '00000000000000000000000000000001'
DEFAULT_FILE_SIZE = 1
FILE_NAME = 'test-file'
DEFAULT_SUBMITTER_ID = '0'
DEFAULT_UUID = 'bef870b0-1d2a-4873-b0db-14994b2f89bd'
DEFAULT_URL = generate_s3_url(
    host=SUBMISSION['host'],
    bucket=SUBMISSION['bucket'],
    program=PROGRAM,
    project=PROJECT,
    uuid=DEFAULT_UUID,
    file_name=FILE_NAME,
)
# Regex because sometimes you don't get to upload a UUID, and the UUID is
# part of the s3 url.
UUID_REGEX = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
REGEX_URL = r's3://{}/{}/{}/{}/{}/{}'.format(
    SUBMISSION['host'],
    SUBMISSION['bucket'],
    PROGRAM,
    PROJECT,
    UUID_REGEX,
    FILE_NAME,
)

DEFAULT_METADATA_FILE = {
    'type': 'experimental_metadata',
    'data_type': 'Experimental Metadata',
    'file_name': FILE_NAME,
    'md5sum': DEFAULT_FILE_HASH,
    'data_format': 'some_format',
    'submitter_id': DEFAULT_SUBMITTER_ID,
    'experiments': {
        'submitter_id': 'BLGSP-71-06-00019'
    },
    'data_category': 'data_file',
    'file_size': DEFAULT_FILE_SIZE,
    'state_comment': '',
    'urls': DEFAULT_URL
}


def submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp):
    put_cgci_blgsp(client, admin)

    # first submit experiment
    data = json.dumps({
        'type': 'experiment',
        'submitter_id': 'BLGSP-71-06-00019',
        'projects': {
            'id': 'daa208a7-f57a-562c-a04a-7a7c77542c98'
        }
    })
    resp = client.put(BLGSP_PATH, headers=submitter, data=data)
    assert resp.status_code == 200, resp.data


def submit_metadata_file(client, admin, submitter, data=None, create_project=False):
    data = data or DEFAULT_METADATA_FILE
    if create_project:
        put_cgci_blgsp(client, admin)
    data = json.dumps(data)
    resp = client.put(BLGSP_PATH, headers=submitter, data=data)
    return resp


def assert_alias_created(
        indexd_client, project_id='CGCI-BLGSP', submitter_id=DEFAULT_SUBMITTER_ID):
    alias = '{}/{}'.format(project_id, submitter_id)
    doc_by_alias = indexd_client.global_get(alias)
    assert doc_by_alias
    assert doc_by_alias.size == DEFAULT_FILE_SIZE
    assert doc_by_alias.hashes.get('md5') == DEFAULT_FILE_HASH


def assert_single_record(indexd_client):
    records = [r for r in indexd_client.list()]
    assert len(records) == 1
    return records[0]


def test_data_file_not_indexed(
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test node and data file creation when neither exist and no ID is provided.
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    resp = submit_metadata_file(client, admin, submitter)

    # response
    assert_positive_response(resp)
    entity = assert_single_entity_from_response(resp)
    assert entity['action'] == 'create'

    indexd_doc = assert_single_record(indexd_client)

    # won't have an exact match because of the way URLs are generated
    # with a UUID in them
    assert re.match(REGEX_URL, indexd_doc.urls[0])

    # alias creation
    assert_alias_created(indexd_client)

    # response
    assert_positive_response(resp)
    entity = assert_single_entity_from_response(resp)
    assert entity['action'] == 'create'

    # make sure uuid in node is the same as the uuid from index
    # FIXME this is a temporary solution so these tests will probably
    #       need to change in the future
    assert entity['id'] == indexd_doc.did


def test_data_file_not_indexed_id_provided(
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test node and data file creation when neither exist and an ID is provided.
    That ID should be used for the node and file index creation
    """

    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    file = copy.deepcopy(DEFAULT_METADATA_FILE)
    file['id'] = DEFAULT_UUID
    resp = submit_metadata_file(
        client, admin, submitter, data=file)

    # response
    assert_positive_response(resp)
    entity = assert_single_entity_from_response(resp)
    assert entity['action'] == 'create'

    # indexd records
    indexd_doc = assert_single_record(indexd_client)

    # index creation
    assert indexd_doc.did == DEFAULT_UUID
    assert indexd_doc.hashes.get('md5') == DEFAULT_FILE_HASH
    assert DEFAULT_URL in indexd_doc.urls_metadata

    # alias creation
    assert_alias_created(indexd_client)


@pytest.mark.parametrize('id_provided', [False, True])
def test_data_file_already_indexed(
        id_provided,
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test submitting when the file is already indexed in the index client and
    1. ID is not provided. sheepdog should fall back on the hash/size of the file
    to find it in indexing service.
    2. ID is provided
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    # submit metadata file once
    metadata_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    metadata_file['id'] = DEFAULT_UUID

    resp = submit_metadata_file(client, admin, submitter, data=metadata_file)
    record = assert_single_record(indexd_client)
    entity = assert_single_entity_from_response(resp)
    assert_positive_response(resp)
    assert entity['action'] == 'create'

    # submit same metadata file again (with or without id provided)
    metadata_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    if id_provided:
        metadata_file['id'] = entity['id']

    resp1 = submit_metadata_file(client, admin, submitter, data=metadata_file)
    record1 = assert_single_record(indexd_client)
    entity1 = assert_single_entity_from_response(resp1)
    assert_positive_response(resp1)
    assert entity1['action'] == 'update'

    # check that record did not change
    assert record.to_json() == record1.to_json()

    # make sure uuid in node is the same as the uuid from index
    # FIXME this is a temporary solution so these tests will probably
    #       need to change in the future
    assert entity['id'] == record1.did


@pytest.mark.parametrize(
    'new_urls,id_provided', [
        (['some/new/url/location/to/add'], False),
        (['some/new/url/location/to/add'], True),
        ([DEFAULT_URL, 'some/new/url/location/to/add', 'some/other/url'], False),
        ([DEFAULT_URL, 'some/new/url/location/to/add', 'some/other/url'], True),
    ]
)
def test_data_file_update_urls(
        new_urls, id_provided,
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test submitting the same data again but updating the URL field (should
    get added to the indexed file in index service).
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    # submit metadata_file once
    submit_metadata_file(client, admin, submitter)
    record = assert_single_record(indexd_client)

    # now submit again but change url
    updated_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    updated_file['urls'] = ','.join(new_urls)
    if id_provided:
        updated_file['id'] = record.did

    resp = submit_metadata_file(
        client, admin, submitter, data=updated_file)

    record1 = assert_single_record(indexd_client)
    entity = assert_single_entity_from_response(resp)
    assert_positive_response(resp)
    assert entity['action'] == 'update'
    # make sure uuid in node is the same as the uuid from index
    # FIXME this is a temporary solution so these tests will probably
    #       need to change in the future
    assert entity['id'] == record.did

    # make sure original url and new url are in the resulting document
    assert set(record1.urls) == set(record.urls) or set(new_urls)


""" ----- TESTS THAT SHOULD RESULT IN SUBMISSION FAILURES ARE BELOW  ----- """


def test_data_file_update_url_invalid_id(
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test submitting the same data again (with the WRONG id provided).
    i.e. ID provided doesn't match the id from the index service for the file
         found with the hash/size provided

    FIXME: the 1:1 between node id and index/file id is temporary so this
           test may need to be modified in the future
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    # submit metadata file once
    metadata_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    metadata_file['id'] = DEFAULT_UUID
    submit_metadata_file(client, admin, submitter, data=metadata_file)
    record = assert_single_record(indexd_client)

    # now submit again but change url and use wrong ID
    new_url = 'some/new/url/location/to/add'
    updated_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    updated_file['urls'] = new_url
    updated_file['id'] = DEFAULT_UUID.replace('1', '2')  # use wrong ID
    resp1 = submit_metadata_file(
        client, admin, submitter, data=updated_file)

    record1 = assert_single_record(indexd_client)

    # make sure it fails
    assert_negative_response(resp1)
    assert_single_entity_from_response(resp1)

    # make sure that indexd record did not change
    assert record.to_json() == record1.to_json()


@pytest.mark.parametrize('id_provided', [False, True])
def test_data_file_update_url_different_file_not_indexed(
        id_provided,
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test submitting the different data (with NO id provided) and updating the
    URL field.

    HOWEVER the file hash and size in the new data do NOT match the previously
    submitted data. The file hash/size provided does NOT
    match an already indexed file. e.g. The file is not yet indexed.

    The assumption is that the user is attempting to UPDATE the index
    with a new file but didn't provide a full id, just the same submitter_id
    as before.

    Without an ID provided, sheepdog falls back on secondary keys (being
    the submitter_id/project). There is already a match for that, BUT
    the provided file hash/size is different than the previously submitted one.
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    # submit metadata file once
    metadata_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    metadata_file['id'] = DEFAULT_UUID
    submit_metadata_file(client, admin, submitter, data=metadata_file)
    record = assert_single_record(indexd_client)

    # now submit again but change url, hash and file size
    new_url = 'some/new/url/location/to/add'
    updated_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    updated_file['urls'] = new_url
    updated_file['md5sum'] = DEFAULT_FILE_HASH.replace('0', '2')
    updated_file['file_size'] = DEFAULT_FILE_SIZE + 1
    if id_provided:
        updated_file['id'] = DEFAULT_UUID

    resp1 = submit_metadata_file(
        client, admin, submitter, data=updated_file)
    record1 = assert_single_record(indexd_client)

    # make sure it fails
    assert_negative_response(resp1)
    assert_single_entity_from_response(resp1)

    # make sure that indexd record did not change
    assert record.to_json() == record1.to_json()


@patch('sheepdog.transactions.upload.sub_entities.FileUploadEntity.get_file_from_index_by_hash')
@patch('sheepdog.transactions.upload.sub_entities.FileUploadEntity.get_file_from_index_by_uuid')
@patch('sheepdog.transactions.upload.sub_entities.FileUploadEntity._create_index')
@patch('sheepdog.transactions.upload.sub_entities.FileUploadEntity._create_alias')
def test_data_file_update_url_id_provided_different_file_already_indexed(
        create_alias, create_index, get_index_uuid, get_index_hash,
        client, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Test submitting the same data again (with the id provided) and updating the
    URL field (should get added to the indexed file in index service).

    HOWEVER the file hash and size in the new data MATCH A DIFFERENT
    FILE in the index service that does NOT have the id provided.

    The assumption is that the user is attempting to UPDATE the index
    with a new file they've already submitted under a different id.

    FIXME At the moment, we do not allow updating like this
    """
    submit_first_experiment(client, pg_driver, admin, submitter, cgci_blgsp)

    document_with_id = MagicMock()
    document_with_id.did = DEFAULT_UUID
    document_with_id.urls = [DEFAULT_URL]

    different_file_matching_hash_and_size = MagicMock()
    different_file_matching_hash_and_size.did = '14fd1746-61bb-401a-96d2-342cfaf70000'
    different_file_matching_hash_and_size.urls = [DEFAULT_URL]

    get_index_uuid.return_value = document_with_id
    get_index_hash.return_value = different_file_matching_hash_and_size

    submit_metadata_file(client, admin, submitter)

    # now submit again but change url
    new_url = 'some/new/url/location/to/add'
    updated_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    updated_file['urls'] = new_url
    updated_file['id'] = DEFAULT_UUID
    updated_file['md5sum'] = DEFAULT_FILE_HASH.replace('0', '2')
    updated_file['file_size'] = DEFAULT_FILE_SIZE + 1
    resp = submit_metadata_file(
        client, admin, submitter, data=updated_file)

    # no index or alias creation
    assert not create_index.called
    assert not create_alias.called

    # make sure original url is still there and new url is NOT
    assert DEFAULT_URL in document_with_id.urls
    assert DEFAULT_URL in different_file_matching_hash_and_size.urls
    assert new_url not in document_with_id.urls
    assert new_url not in different_file_matching_hash_and_size.urls

    # response
    assert_negative_response(resp)
    assert_single_entity_from_response(resp)


@pytest.mark.config_toggle(parameter='ENFORCE_FILE_HASH_SIZE_UNIQUENESS', value=False)
def test_dont_enforce_file_hash_size_uniqueness(
        client_toggled, pg_driver, admin, submitter, cgci_blgsp, indexd_client):
    """
    Check that able to submit two files with different did and urls but
    duplicate hash and size if ENFORCE_FILE_HASH_SIZE_UNIQUENESS set to False
    """

    submit_first_experiment(client_toggled, pg_driver, admin, submitter, cgci_blgsp)

    # submit metadata file once
    metadata_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    metadata_file['id'] = DEFAULT_UUID
    submit_metadata_file(client_toggled, admin, submitter, data=metadata_file)
    assert_single_record(indexd_client)

    # release_indexd_doc(pg_driver, indexd_client, DEFAULT_UUID)
    # now submit again but change url and id
    new_id = DEFAULT_UUID.replace('0', '1')  # use different uuid
    new_url = 'some/new/url/location/to/add'

    updated_file = copy.deepcopy(DEFAULT_METADATA_FILE)
    updated_file['urls'] = new_url
    updated_file['id'] = new_id

    # release so that a new indexd document can be made
    submit_metadata_file(
        client_toggled, admin, submitter,
        data=updated_file,
    )

    # check that both are inserted into indexd and have correct urls
    records = [_ for _ in indexd_client.list()]
    assert len(records) == 2
    assert indexd_client.get(DEFAULT_UUID).urls == [DEFAULT_URL]
    assert indexd_client.get(new_id).urls == [new_url]


def test_is_updatable_file(client, pg_driver, indexd_client):
    """Test _is_updatable_file_node method
    """

    did = 'bef870b0-1d2a-4873-b0db-14994b2f89bd'
    url = '/some/url'

    # Create dummy file node and corresponding indexd record
    node = SubmittedAlignedReads(did)
    indexd_client.create(
        did=did,
        urls=[url],
        hashes={'md5': '0'*32},
        size=1,
    )
    ALLOWED_STATES = [
        'registered',
        'uploading',
        'uploaded',
        'validating',
    ]

    DISALLOWED_STATES = [
        'validated',
    ]
    transaction = MagicMock()
    transaction.indexd = indexd_client
    entity = FileUploadEntity(transaction)
    entity.s3_url = url

    for file_state in ALLOWED_STATES:
        # set node's url state in indexd
        indexd_doc = indexd_client.get(did)
        set_indexd_state(indexd_doc, url, file_state)

        # check if updatable
        assert entity.is_updatable_file_node(node)

    for file_state in DISALLOWED_STATES:
        # set node's url state in indexd
        indexd_doc = indexd_client.get(did)
        set_indexd_state(indexd_doc, url, file_state)
        # check if not updatable
        assert not entity.is_updatable_file_node(node)
