from cafe.drivers.unittest import fixtures
from .utils import config
from .utils import client
from .utils.schema import auth
from .utils.schema import deuce_schema

from collections import namedtuple

import base64
import hashlib
import json
import jsonschema
import msgpack
import os
import random
import re
import string
import time

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

Block = namedtuple('Block', 'Id Data')
File = namedtuple('File', 'Id Url')
Storage = namedtuple('Storage', 'Id BlockId')


class TestBase(fixtures.BaseTestFixture):
    """
    Fixture for Deuce API Tests
    """

    @classmethod
    def setUpClass(cls):
        """
        Initialization of Deuce Client
        """

        super(TestBase, cls).setUpClass()
        cls.config = config.deuceConfig()
        cls.auth_config = config.authConfig()
        cls.auth_token = None
        cls.storage_config = config.storageConfig()
        cls.service_catalog_b64 = ''
        cls.tenantid = None
        cls.region = cls.storage_config.region
        if cls.config.use_auth:
            cls.a_client = client.AuthClient(cls.auth_config.base_url)
            cls.a_resp = cls.a_client.get_auth_token(cls.auth_config.user_name,
                                                     cls.auth_config.api_key)
            jsonschema.validate(cls.a_resp.json(), auth.authentication)
            resp = cls.a_resp.json()
            cls.auth_token = resp['access']['token']['id']

            cls.tenantid = resp['access']['token']['tenant']['id']
            url_type = 'internalURL' if cls.storage_config.internal_url \
                else 'publicURL'
            if cls.auth_config.use_service_catalog:
                cls.service_catalog_b64 = base64.b64encode(
                    cls.a_resp.text.encode('utf-8'))
        cls.client = client.BaseDeuceClient(cls.config.base_url,
                                            cls.config.version,
                                            cls.auth_token,
                                            cls.service_catalog_b64,
                                            cls.tenantid)

        cls.vaults = []
        cls.blocks = []
        cls.api_version = cls.config.version
        cls.skip_diagnostics = cls.config.skip_diagnostics
        cls.soft_vault_list_validation = cls.config.soft_vault_list_validation

    @classmethod
    def tearDownClass(cls):
        """
        Deletes the added resources
        """
        super(TestBase, cls).tearDownClass()

    @classmethod
    def id_generator(cls, size):
        """
        Return an alphanumeric string of size
        """

        return ''.join(random.choice(string.ascii_letters +
            string.digits + '-_') for _ in range(size))

    def setUp(self):
        super(TestBase, self).setUp()

    def tearDown(self):
        if hasattr(self, '_resultForDoCleanups'):
            if any(r for r in self._resultForDoCleanups.failures
                   if self._custom_test_name_matches_result(
                       self._testMethodName, r)):
                self._reporter.stop_test_metrics(self._testMethodName,
                                                 'Failed')
            elif any(r for r in self._resultForDoCleanups.errors
                     if self._custom_test_name_matches_result(
                         self._testMethodName, r)):
                self._reporter.stop_test_metrics(self._testMethodName,
                                                 'ERRORED')
            else:
                super(TestBase, self).tearDown()
        else:
            super(TestBase, self).tearDown()

    def _custom_test_name_matches_result(self, name, test_result):
        """
        Function used to compare test name with the information in test_result
        Used with Nosetests
        """

        try:
            result = test_result[0]
            testMethodName = result.__str__().split()[0]
        except:
            return False
        return testMethodName == name

    def assertHeaders(self, headers, json=False, binary=False,
                      lastmodified=False, contentlength=None,
                      refcount=None, blockid=None, storageid=None,
                      allow=None, location=False, orphan=None, size=None,
                      skip_contentlength=False):
        """Basic http header validation"""

        self.assertIsNotNone(headers['transaction-id'])
        if not skip_contentlength:
            self.assertIsNotNone(headers['content-length'])
        if json:
            self.assertEqual(headers['content-type'],
                             'application/json; charset=utf-8')
        if binary:
            content_type = headers['content-type'].split(';')[0]
            self.assertEqual(content_type,
                             'application/octet-stream')
        if lastmodified:
            self.assertIn('X-Ref-Modified', headers)
            try:
                time.ctime(int(headers['X-Ref-Modified']))
            except:
                self.fail('Unable to process X-Ref-Modified {0}'.format(
                    headers['X-Ref-Modified']))

        if contentlength is not None:
            if 'content-length' in headers:
                self.assertEqual(int(headers['content-length']), contentlength)

        if refcount is not None:
            self.assertIn('X-Block-Reference-Count', headers)
            self.assertEqual(int(headers['X-Block-Reference-Count']), refcount)

        if blockid is not None:
            self.assertIn('X-Block-Id', headers)
            self.assertEqual(headers['X-Block-Id'], blockid)

        if storageid is not None:
            self.assertIn('X-Storage-Id', headers)
            self.assertEqual(headers['X-Storage-Id'], storageid)

        if allow is not None:
            self.assertIn('Allow', headers)
            self.assertEqual(headers['Allow'], allow)

        if location:
            self.assertIn('X-Block-Location', headers)

        if orphan is not None:
            self.assertIn('X-Block-Orphaned', headers)
            self.assertEqual(headers['X-Block-Orphaned'], orphan)

        if size is not None:
            self.assertIn('X-Block-Size', headers)
            self.assertEqual(int(headers['X-Block-Size']), size)

    def assertUrl(self, url, base=False, vaults=False, vaultspath=False,
                  blocks=False, blockpath=False, files=False, filepath=False,
                  fileblock=False, storage=False, nextlist=False):
        """Check that the url provided has information according to the flags
        passed
        """

        msg = 'url: {0}'.format(url)
        u = urlparse.urlparse(url)
        self.assertIn(u.scheme, ['http', 'https'])

        if base:
            self.assertEqual(u.path, '/{0}'.format(self.api_version), msg)

        if vaults:
            self.assertEqual(u.path, '/{0}/vaults'.format(self.api_version,
                                                          msg))

        if vaultspath:
            valid = re.compile('/{0}/vaults/[a-zA-Z0-9\-_]*'
                               ''.format(self.api_version))
            self.assertIsNotNone(valid.match(u.path), msg)

        if blocks:
            self.assertEqual(u.path, '/{0}/vaults/{1}/blocks'
                             ''.format(self.api_version, self.vaultname), msg)

        if blockpath:
            valid = re.compile('/{0}/vaults/{1}/blocks/[a-zA-Z0-9\-]*'
                               ''.format(self.api_version, self.vaultname))
            self.assertIsNotNone(valid.match(u.path), msg)

        if files:
            self.assertEqual(u.path, '/{0}/vaults/{1}/files'
                             ''.format(self.api_version, self.vaultname), msg)

        if filepath:
            valid = re.compile('/{0}/vaults/{1}/files/[a-zA-Z0-9\-_]*'
                               ''.format(self.api_version, self.vaultname))
            self.assertIsNotNone(valid.match(u.path), msg)

        if fileblock:
            valid = re.compile('/{0}/vaults/{1}/files/[a-zA-Z0-9\-_]*/blocks'
                               ''.format(self.api_version, self.vaultname))
            self.assertIsNotNone(valid.match(u.path), msg)

        if storage:
            self.assertEqual(u.path, '/{0}/vaults/{1}/storage/blocks'
                             ''.format(self.api_version, self.vaultname), msg)

        if nextlist:
            query = urlparse.parse_qs(u.query)
            self.assertIn('marker', query, msg)
            self.assertIn('limit', query, msg)

    def _assert_empty_response(self, resp, code, skip_contentlength=False):
        """Validation of empty responses"""

        self.assertEqual(resp.status_code, code,
                         'Status code returned: {0} . '
                         'Expected {1}'.format(resp.status_code, code))
        self.assertHeaders(resp.headers, contentlength=0,
                           skip_contentlength=skip_contentlength)
        self.assertEqual(len(resp.content), 0)

    def _assert_json_response(self, resp, code):
        """Validation of json responses"""

        self.assertEqual(resp.status_code, code,
                         'Status code returned: {0} . '
                         'Expected {1}'.format(resp.status_code, code))
        self.assertHeaders(resp.headers, json=True)

    def assert_404_response(self, resp, skip_contentlength=False):
        """Basic validation of a 404 response"""

        self._assert_empty_response(resp, 404,
                                    skip_contentlength=skip_contentlength)

    def assert_201_response(self, resp):
        """Basic validation of a 201 response"""

        self._assert_empty_response(resp, 201)

    def assert_200_response(self, resp):
        """Basic validation of a 200 response"""

        self._assert_json_response(resp, 200)

    def assert_204_response(self, resp, skip_contentlength=True):
        """Basic validation of a 204 response"""

        self._assert_empty_response(resp, 204,
                                    skip_contentlength=skip_contentlength)

    def assert_409_response(self, resp):
        """Basic validation of a 409 response"""

        self._assert_json_response(resp, 409)

    def assert_412_response(self, resp):
        """Basic validation of a 412 response"""

        self._assert_json_response(resp, 412)

    def assert_uuid4(self, value):
        """Validate the value is a uuid4"""

        self._assert_uuid(4, value)

    def assert_uuid5(self, value):
        """Validate the value is a uuid5"""

        self._assert_uuid(5, value)

    def _assert_uuid(self, version, value):
        """Validate the value is a uuid"""

        self.assertRegexpMatches(value,
                r'^[a-z0-9]{8}\-[a-z0-9]{4}\-' + str(version) +
                '[a-z0-9]{3}\-[ab89]'
                '[a-z0-9]{3}\-[a-z0-9]{12}$')

    def _create_empty_vault(self, vaultname=None, size=50):
        """
        Test Setup Helper: Creates an empty vault
        If vaultname is provided, the vault is created using that name.
        If not, an alphanumeric vaultname of a given size is generated
        """

        if vaultname:
            self.vaultname = vaultname
        else:
            self.vaultname = self.id_generator(size)
        resp = self.client.create_vault(self.vaultname)
        return 201 == resp.status_code

    def create_empty_vault(self, vaultname=None, size=50):
        """
        Test Setup Helper: Creates an empty vault
        If vaultname is provided, the vault is created using that name.
        If not, an alphanumeric vaultname of a given size is generated

        Exception is raised if the operation is not successful
        """
        if not self._create_empty_vault(vaultname, size):
            raise Exception('Failed to create vault')
        self.vaults.append(self.vaultname)
        self.blocks = []
        self.files = []
        self.storage = []
        self.modified_times = []

    def generate_block_data(self, block_data=None, size=30720):
        """
        Test Setup Helper: Generates block data and adds it to the internal
        block list
        """

        if block_data is not None:
            self.block_data = block_data
        else:
            self.block_data = os.urandom(size)
        self.blockid = hashlib.new('sha1', self.block_data).hexdigest()
        self.blocks.append(Block(Id=self.blockid, Data=self.block_data))

    def _upload_block(self, block_data=None, size=30720):
        """
        Test Setup Helper: Uploads a block
        If block_data is used if provided.
        If not, a random block of data of the specified size is used
        """
        self.generate_block_data(block_data, size)
        self.resp = self.client.upload_block(self.vaultname, self.blockid,
                                        self.block_data)
        return 201 == self.resp.status_code

    def upload_block(self, block_data=None, size=30720):
        """
        Test Setup Helper: Uploads a block
        If block_data is used if provided.
        If not, a random block of data of the specified size is used

        Exception is raised if the operation is not successful
        """
        if not self._upload_block(block_data, size):
            raise Exception('Failed to upload block')
        self.storageid = self.resp.headers['x-storage-id']
        self.storage.append(Storage(Id=self.storageid, BlockId=self.blockid))
        resp = self.client.block_head(self.vaultname, self.blockid)
        if resp.status_code != 204:
            raise Exception('Could not HEAD block {0}'.format(self.blockid))
        self.modified = int(resp.headers['x-ref-modified'])
        self.modified_times.append(self.modified)

    def _upload_multiple_blocks(self, nblocks, size=30720):
        """
        Test Setup Helper: Uploads multiple blocks using msgpack
        """
        prev_blocks = self.blocks[:]
        [self.generate_block_data(size=size) for _ in range(nblocks)]
        # uploaded new generated blocks
        uploaded = list(set(self.blocks) - set(prev_blocks))
        data = dict([(block.Id, block.Data) for block in uploaded])
        msgpack_data = msgpack.packb(data)
        resp = self.client.upload_multiple_blocks(self.vaultname, msgpack_data)
        return 201 == resp.status_code

    def upload_multiple_blocks(self, nblocks, size=30720):
        """
        Test Setup Helper: Uploads multiple blocks using msgpack

        Exception is raised if the operation is not successful
        """
        if not self._upload_multiple_blocks(nblocks, size):
            raise Exception('Failed to upload multiple blocks')
        for block in self.blocks:
            resp = self.client.block_head(self.vaultname, block.Id)
            if resp.status_code != 204:
                raise Exception('Could not HEAD block {0}'.format(block.Id))
            self.storage.append(Storage(Id=resp.headers['x-storage-id'],
                BlockId=block.Id))
            self.modified_times.append(int(resp.headers['x-ref-modified']))
        self.storageid = self.storage[-1].Id
        self.modified = self.modified_times[-1]

    def _create_new_file(self):
        """
        Test Setup Helper: Creates a file
        """

        self.resp = self.client.create_file(self.vaultname)
        return 201 == self.resp.status_code

    def create_new_file(self):
        """
        Test Setup Helper: Creates a file

        Exception is raised if the operation is not successful
        """

        if not self._create_new_file():
            raise Exception('Failed to create a file')
        self.fileurl = self.resp.headers['location']
        self.fileid = self.resp.headers['X-File-Id']
        self.files.append(File(Id=self.fileid, Url=self.fileurl))
        self.filesize = 0

    def assign_all_blocks_to_file(self, offset_divisor=None):
        """
        Test Setup Helper: Assigns all blocks to the file

        Exception is raised if the operation is not successful
        """

        if not self._assign_blocks_to_file(offset_divisor=offset_divisor):
            raise Exception('Failed to assign blocks to file')
        self.filesize += self.blocks_size

    def _assign_blocks_to_file(self, offset=0, blocks=[],
                              offset_divisor=None, file_url=None):
        """
        Test Setup Helper: Assigns blocks to the file
        """

        block_list = list()
        self.blocks_size = 0
        if len(blocks) == 0:
            blocks = range(len(self.blocks))
        if not file_url:
            file_url = self.fileurl

        for index in blocks:
            block_info = self.blocks[index]
            block_list.append([block_info.Id, offset])
            if offset_divisor:
                offset += len(block_info.Data) / offset_divisor
            else:
                offset += len(block_info.Data)
            self.blocks_size += len(block_info.Data)

        resp = self.client.assign_to_file(json.dumps(block_list),
                                          alternate_url=file_url)
        return 200 == resp.status_code

    def assign_blocks_to_file(self, offset=0, blocks=[],
                              offset_divisor=None, file_url=None):
        """
        Test Setup Helper: Assigns blocks to the file

        Exception is raised if the operation is not successful
        """

        if not self._assign_blocks_to_file(offset, blocks, offset_divisor,
                                           file_url):
            raise Exception('Failed to assign blocks to file')
        self.filesize += self.blocks_size

    def _finalize_file(self, file_url=None):
        """
        Test Setup Helper: Finalizes the file
        """

        if not file_url:
            file_url = self.fileurl
        resp = self.client.finalize_file(filesize=self.filesize,
                                         alternate_url=file_url)
        return 200 == resp.status_code

    def finalize_file(self, file_url=None):
        """
        Test Setup Helper: Finalizes the file

        Exception is raised if the operation is not successful
        """

        if not self._finalize_file(file_url):
            raise Exception('Failed to finalize file')
