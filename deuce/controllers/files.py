from pecan import conf, expose, request, response
from pecan.core import abort
from pecan.rest import RestController

import deuce
from deuce.controllers.fileblocks import FileBlocksController
from deuce.model import Vault, Block, File
from deuce.util import FileCat
from deuce.util import set_qs


class FilesController(RestController):

    blocks = FileBlocksController()

    @expose('json')
    def get_all(self, vault_id):

        vault = Vault.get(request.project_id, vault_id)

        if not vault:
            abort(404)

        inmarker = request.params.get('marker')

        limit = int(request.params.get('limit',
           conf.api_configuration.max_returned_num))

        # The +1 is to fetch one past the user's
        # requested limit so that we can determine
        # if the list was truncated or not
        files = vault.get_files(inmarker, limit + 1)

        resp = list(files)

        # Note: the list may not actually be truncated
        truncated = len(resp) == limit + 1

        outmarker = resp.pop().file_id if truncated else None

        if outmarker:
            query_args = {'marker': outmarker}
            query_args['limit'] = limit

            returl = set_qs(request.url, query_args)

            response.headers["X-Next-Batch"] = returl

        return resp

    @expose()
    def get_one(self, vault_id, file_id):
        """Fetches, re-assembles and streams a single
        file out of Deuce"""

        vault = Vault.get(request.project_id, vault_id)
        if not vault:
            abort(404)

        f = vault.get_file(file_id)

        if not f:
            abort(404)

        block_gen = deuce.metadata_driver.create_file_block_generator(
            request.project_id, vault_id, file_id)

        objs = deuce.storage_driver.create_blocks_generator(
            request.project_id, vault_id, block_gen)

        response.body_file = FileCat(objs)
        response.status_code = 200

    @expose('json')
    def post(self, vault_id, file_id=None):
        """Initializes a new file. The location of
        the new file is returned in the Location
        header
        """

        if file_id == "":  # i.e .../files/
            abort(404)

        vault = Vault.get(request.project_id, vault_id)
        if not vault:
            abort(404)

        if file_id:
            return self._assign(vault, vault_id, file_id)

        file = vault.create_file()

        response.headers["Location"] = "files/%s" % file.file_id
        response.status_code = 201  # Created

    def _assign(self, vault, vault_id, file_id):

        f = vault.get_file(file_id)

        if not f:
            abort(404)

        # Fileid with an empty body will finalize the file.
        if not request.body:
            deuce.metadata_driver.finalize_file(request.project_id,
                vault_id, file_id)

            return

        if f.finalized:
            # A finalized file cannot be
            # modified
            # TODO: Determine a better, more precise
            #       status code
            abort(400)

        blocks = request.json_body['blocks']

        missing_blocks = list()

        for mapping in blocks:

            block_id = mapping['id']
            offset = mapping['offset']

            if not deuce.metadata_driver.has_block(request.project_id,
                    vault_id, block_id):

                missing_blocks.append(block_id)

            deuce.metadata_driver.assign_block(request.project_id, vault_id,
                file_id, mapping['id'], mapping['offset'])

        return missing_blocks
