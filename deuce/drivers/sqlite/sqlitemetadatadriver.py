from functools import lru_cache

from deuce import conf
import deuce
import importlib


from deuce.drivers.metadatadriver import MetadataStorageDriver,\
    OverlapError, GapError, ConstraintError

# SQL schemas. Note: the schema is versions
# in such a way that new instances always start
# with user version 1, then proceeed to upgrade
# through each version until we get to the latest.

schemas = list()

schemas.append([
    """
    CREATE TABLE files
    (
        projectid TEXT NOT NULL,
        vaultid TEXT NOT NULL,
        fileid TEXT NOT NULL,
        finalized INTEGER NOT NULL DEFAULT 0,
        size INTEGER DEFAULT 0,
        PRIMARY KEY(projectid, vaultid, fileid)
    )
    """,
    """
    CREATE TABLE fileblocks
    (
        projectid TEXT NOT NULL,
        vaultid TEXT NOT NULL,
        fileid TEXT NOT NULL,
        blockid TEXT NOT NULL,
        offset INTEGER NOT NULL,
        UNIQUE (projectid, vaultid, fileid, blockid, offset)
    )
    """,
    """
    CREATE TABLE blocks
    (
        projectid TEXT NOT NULL,
        vaultid TEXT NOT NULL,
        blockid TEXT NOT NULL,
        storageid TEXT NOT NULL,
        size INTEGER NOT NULL,
        reftime DATETIME NOT NULL,
        isinvalid BOOLEAN NOT NULL DEFAULT 0,
        PRIMARY KEY(projectid, vaultid, blockid)
    )
    """,
    """
    CREATE TABLE vaults
    (
        projectid TEXT NOT NULL,
        vaultid TEXT NOT NULL,
        PRIMARY KEY(projectid, vaultid)
    )
    """
])  # Version 1

CURRENT_DB_VERSION = len(schemas)

SQL_CREATE_VAULT = '''
    INSERT OR REPLACE INTO vaults
    (projectid, vaultid)
    VALUES (:projectid, :vaultid)
'''

SQL_DELETE_VAULT = '''
    DELETE FROM vaults
    where projectid=:projectid
    AND vaultid=:vaultid
'''

SQL_GET_ALL_VAULT = '''
    SELECT vaultid
    FROM vaults
    WHERE projectid = :projectid
    AND vaultid >= :marker
    ORDER BY vaultid
    LIMIT :limit
'''

SQL_CREATE_FILE = '''
    INSERT INTO files (projectid, vaultid, fileid)
    VALUES (:projectid, :vaultid, :fileid)
'''

SQL_GET_BLOCK = '''
    SELECT size
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
    AND isinvalid = 0
'''

SQL_GET_FILE = '''
    SELECT finalized
    FROM files
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid
'''

SQL_GET_FILE_SIZE = '''
    SELECT size
    FROM files
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid
'''

SQL_DELETE_FILE = '''
    DELETE FROM files
    where projectid=:projectid
    AND vaultid=:vaultid
    AND fileid=:fileid
'''

SQL_GET_ALL_FILE_BLOCKS = '''
    SELECT blockid, offset
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid
    ORDER BY offset
'''
SQL_GET_BAD_BLOCKS = '''
    SELECT blockid
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND isinvalid = 1
'''

SQL_GET_FILE_PER_BLOCK = '''
    SELECT fileid
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
'''

SQL_UPDATE_REF_TIME_BLOCKS_IN_FILE = '''
    UPDATE blocks
    SET reftime = strftime('%s', 'now')
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid IN (SELECT blockid
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid)
'''

SQL_GET_COUNT_ALL_FILE_BLOCKS = '''
    SELECT COUNT(DISTINCT(blockid))
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
'''

SQL_GET_FILE_BLOCKS = '''
    SELECT blockid, offset
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid
    AND offset >= :offset
    ORDER BY offset
    LIMIT :limit
'''

SQL_DELETE_FILE_BLOCKS_FOR_FILE = '''
    DELETE FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND fileid = :fileid
'''

SQL_GET_ALL_BLOCKS = '''
    SELECT blockid
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid >= :marker
    order by blockid
    LIMIT :limit
'''

SQL_GET_STORAGE_ID = '''
    SELECT storageid
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
'''

SQL_GET_BLOCK_ID = '''
    SELECT blockid
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND storageid = :storageid
'''

SQL_GET_COUNT_ALL_BLOCKS = '''
    SELECT COUNT(DISTINCT(blockid))
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
'''

SQL_GET_ALL_FILES = '''
    SELECT fileid
    FROM files
    WHERE projectid=:projectid
    AND vaultid = :vaultid
    AND fileid >= :marker
    AND finalized = :finalized
    order by fileid
    LIMIT :limit
'''

SQL_GET_COUNT_ALL_FILES = '''
    SELECT COUNT(DISTINCT(fileid))
    FROM files
    WHERE projectid = :projectid
    AND vaultid = :vaultid
'''


SQL_CREATE_FILEBLOCK_LIST = '''
    SELECT blocks.blockid, fileblocks.offset, blocks.size
    FROM blocks, fileblocks
    WHERE fileblocks.blockid = blocks.blockid
    AND fileblocks.vaultid = blocks.vaultid
    AND fileblocks.projectid = :projectid
    AND fileblocks.vaultid = :vaultid
    AND fileblocks.fileid = :fileid
    AND blocks.isinvalid = 0
    ORDER by offset
'''

SQL_FINALIZE_FILE = '''
    UPDATE files
    SET finalized=1, size=:file_size
    WHERE projectid=:projectid
    AND fileid=:fileid
    AND vaultid=:vaultid
'''

SQL_ASSIGN_BLOCK_TO_FILE = '''
    INSERT OR REPLACE INTO fileblocks
    (projectid, vaultid, fileid, blockid, offset)
    VALUES (:projectid, :vaultid, :fileid, :blockid, :offset)
'''

SQL_REGISTER_BLOCK = '''
    INSERT OR REPLACE INTO blocks
    (projectid, vaultid, blockid, storageid, size, reftime, isinvalid)
    VALUES (:projectid, :vaultid, :blockid, :storageid, :blocksize,
    strftime('%s', 'now'), 0)
'''

SQL_UNREGISTER_BLOCK = '''
    DELETE FROM blocks
    WHERE projectid=:projectid AND blockid=:blockid
'''

SQL_MARK_BLOCK_AS_BAD = '''
    UPDATE blocks SET
    isinvalid = 1 WHERE
    projectid = :projectid AND
    vaultid = :vaultid AND
    blockid = :blockid
'''

SQL_MARK_BLOCK_AS_GOOD = '''
    UPDATE blocks SET
    isinvalid = 0 WHERE
    projectid = :projectid AND
    vaultid = :vaultid AND
    blockid = :blockid
'''

SQL_GET_BLOCK_STATUS = '''
    SELECT isinvalid
    FROM blocks
    WHERE projectid=:projectid
    AND blockid = :blockid
    AND vaultid = :vaultid
'''

SQL_GET_BLOCK_REF_COUNT = '''
    SELECT count(*)
    FROM fileblocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
'''

SQL_UPDATE_REF_TIME = '''
    UPDATE blocks
    SET reftime = strftime('%s', 'now')
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
'''

SQL_GET_REF_TIME = '''
    SELECT reftime
    FROM blocks
    WHERE projectid = :projectid
    AND vaultid = :vaultid
    AND blockid = :blockid
'''


class SqliteStorageDriver(MetadataStorageDriver):

    def __init__(self):
        self._dbfile = conf.metadata_driver.sqlite.path

        # Load the driver module according to the configuration
        deuce.db_pack = importlib.import_module(
            conf.metadata_driver.sqlite.db_module)
        self._conn = getattr(deuce.db_pack, 'Connection')(self._dbfile)

        self._do_migrate()

    def _get_user_version(self):
        res = self._conn.execute('pragma user_version')
        row = next(res)
        return row[0]

    def _set_user_version(self, version):
        # NOTE: for whatever reason, pragma's don't seem to
        # work with the built-in query formatter so
        # we just use string formatting here. This should be
        # OK since version is internally generated.
        self._conn.execute('pragma user_version=%d' % version)

    def _do_migrate(self):
        db_ver = self._get_user_version()

        for ver in range(db_ver, CURRENT_DB_VERSION):
            schema = schemas[db_ver]

            for query in schema:
                self._conn.execute(query)

            db_ver = db_ver + 1
            self._set_user_version(db_ver)

    def _determine_marker(self, marker):
        """Determines the default marker to use if
        the passed marker is None, empty string, etc
        """
        return marker or ''

    def create_vault(self, vault_id):
        """Creates a representation of a vault."""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id
        }
        self._conn.execute(SQL_CREATE_VAULT, args)
        self._conn.commit()
        # TODO: check that one row was inserted
        return

    def delete_vault(self, vault_id):
        """Deletes the vault from metadata."""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id
        }

        self._conn.execute(SQL_DELETE_VAULT, args)
        self._conn.commit()
        return

    def create_vaults_generator(self, marker=None, limit=None):
        """Creates and returns a generator that will return
        the vault IDs.
        """

        args = {
            'projectid': deuce.context.project_id,
            'marker': self._determine_marker(marker),
            'limit': self._determine_limit(limit)
        }

        res = self._conn.execute(SQL_GET_ALL_VAULT, args)
        return [row[0] for row in res]

    def get_vault_statistics(self, vault_id):
        """Return the statistics on the vault.

        "param vault_id: The ID of the vault to gather statistics for"""
        res = {}

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id
        }

        def __stats_query(sql_statement, default_value):
            result = self._conn.execute(sql_statement, args)

            try:
                row = next(result)
                return row[0]

            except StopIteration:  # pragma: no cover
                return default_value

            except IndexError:  # pragma: no cover
                return default_value

        def __stats_get_vault_file_count():
            return __stats_query(SQL_GET_COUNT_ALL_FILES, 0)

        def __stats_get_vault_block_count():
            return __stats_query(SQL_GET_COUNT_ALL_BLOCKS, 0)

        # Add any statistics regarding files
        res['files'] = {}
        res['files']['count'] = __stats_get_vault_file_count()

        # Add any statistics regarding blocks
        res['blocks'] = {}
        res['blocks']['count'] = __stats_get_vault_block_count()

        # Add information about bad blocks and bad files

        res['blocks']['bad'], res['files']['bad'] = \
            self.vault_health(vault_id)
        # Add any statistics specific to the Sqlite backend
        res['internal'] = {}

        return res

    def vault_health(self, vault_id):
        '''Returns the number of bad blocks and bad files associated
        with a vault'''

        args = dict(
            projectid=deuce.context.project_id,
            vaultid=vault_id,
        )

        res = self._conn.execute(SQL_GET_BAD_BLOCKS, args)

        bad_blocks = [row[0] for row in res]

        no_of_bad_blocks = len(bad_blocks)

        bad_files = set()

        for block_id in bad_blocks:
            args = dict(
                projectid=deuce.context.project_id,
                vaultid=vault_id,
                blockid=block_id,
            )
            result = self._conn.execute(SQL_GET_FILE_PER_BLOCK, args)
            bad_file = [row[0] for row in result]
            try:
                bad_files.add(bad_file[0])
            except IndexError:
                pass

        no_of_bad_files = len(bad_files)

        return (no_of_bad_blocks, no_of_bad_files)

    def create_file(self, vault_id, file_id):
        """Creates a new file with no blocks and no files"""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }

        self._conn.execute(SQL_CREATE_FILE, args)
        self._conn.commit()

        # TODO: check that one row was inserted
        return file_id

    def file_length(self, vault_id, file_id):
        """Retrieve length the of the file."""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }

        res = self._conn.execute(SQL_GET_FILE_SIZE, args)

        try:
            row = next(res)
            return row[0]
        except StopIteration:
            return 0

    def get_block_storage_id(self, vault_id, block_id):
        """Retrieve storage id for a given block id"""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        res = self._conn.execute(SQL_GET_STORAGE_ID, args)
        try:
            row = next(res)
            return str(row[0])
        except StopIteration:
            return None

    def get_block_metadata_id(self, vault_id, storage_id):
        """Retrieve block id for a given storage id"""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'storageid': storage_id
        }

        res = self._conn.execute(SQL_GET_BLOCK_ID, args)
        try:
            row = next(res)
            return str(row[0])
        except StopIteration:
            return None

    def has_file(self, vault_id, file_id):
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }

        res = self._conn.execute(SQL_GET_FILE, args)

        try:
            row = next(res)
            return True
        except StopIteration:
            return False

    def is_finalized(self, vault_id, file_id):
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }

        res = self._conn.execute(SQL_GET_FILE, args)

        try:
            row = next(res)
            return row[0] == 1
        except StopIteration:
            return False

    def delete_file(self, vault_id, file_id):
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }
        res = self._conn.execute(SQL_UPDATE_REF_TIME_BLOCKS_IN_FILE, args)
        self._conn.commit()

        res = self._conn.execute(SQL_DELETE_FILE, args)
        self._conn.commit()

        res = self._conn.execute(SQL_DELETE_FILE_BLOCKS_FOR_FILE, args)
        self._conn.commit()

    def finalize_file(self, vault_id, file_id, file_size=None):
        """Updates the files table to set a file to finalized and record
        its size. This function makes no assumptions about whether or not
        the file record actually exists"""
        if file_size is None:
            file_size = 0
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id,
            'file_size': file_size
        }

        # Check for gaps and overlaps.
        expected_offset = 0

        res = self._conn.execute(SQL_CREATE_FILEBLOCK_LIST, args)

        for blockid, offset, size in res:
            if offset == expected_offset:
                expected_offset += size
            elif offset < expected_offset:  # Overlap scenario
                raise OverlapError(deuce.context.project_id, vault_id, file_id,
                    blockid, startpos=offset, endpos=expected_offset)
            else:
                raise GapError(deuce.context.project_id, vault_id, file_id,
                    startpos=expected_offset, endpos=offset)

        # Now we must check the very last block
        if file_size and file_size != expected_offset:

            if expected_offset < file_size:
                raise GapError(deuce.context.project_id, vault_id, file_id,
                    expected_offset, file_size)

            else:
                assert expected_offset > file_size

                raise OverlapError(deuce.context.project_id, vault_id, file_id,
                    file_size, startpos=file_size, endpos=expected_offset)

        res = self._conn.execute(SQL_FINALIZE_FILE, args)
        self._conn.commit()
        return None

    def get_block_data(self, vault_id, block_id):
        """Returns the blocksize for this block"""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        res = self._conn.execute(SQL_GET_BLOCK, args)

        try:
            row = next(res)
        except StopIteration:
            raise Exception("No such block: {0}".format(block_id))

        retval = {}
        retval['blocksize'] = list(row)[0]
        return retval

    def get_file_data(self, vault_id, file_id):
        """Returns a tuple representing data for this file"""
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id
        }

        res = self._conn.execute(SQL_GET_FILE, args)

        try:
            row = next(res)
        except StopIteration:
            raise Exception("No such file: {0}".format(file_id))

        return row

    def mark_block_as_bad(self, vault_id, block_id,):
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        self._conn.execute(SQL_MARK_BLOCK_AS_BAD, args)
        self._conn.commit()

    @staticmethod
    def _block_exists(res, check_status):
        if len(res) == 0:
            return False

        # The result should contain exactly
        # one row and one column.
        assert len(res) == 1
        assert len(res[0]) == 1

        if check_status and res[0][0] == 1:
            return False

        return True

    def reset_block_status(self, vault_id, marker=None, limit=None):

        blocks = self.create_block_generator(vault_id, marker,
                                             self._determine_limit(limit))

        def mark_block_as_good(vault_id, block_id):
            args = {
                'projectid': deuce.context.project_id,
                'vaultid': vault_id,
                'blockid': block_id
            }

            self._conn.execute(SQL_MARK_BLOCK_AS_GOOD, args)
            self._conn.commit()

        for block in blocks:
            mark_block_as_good(vault_id, block)

        return blocks[-1:][0] if len(blocks) == \
            self._determine_limit(limit) else None

    def has_block(self, vault_id, block_id, check_status=False):
        # Query the blocks table
        retval = False

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        # This query should only ever return zero or 1 row, so
        # return that value here
        res = list(self._conn.execute(SQL_GET_BLOCK_STATUS, args))

        return SqliteStorageDriver._block_exists(res, check_status)

    def has_blocks(self, vault_id, block_ids, check_status=False):
        results = []

        for block_id in block_ids:
            args = {
                'projectid': deuce.context.project_id,
                'vaultid': vault_id,
                'blockid': block_id
            }

            res = list(self._conn.execute(SQL_GET_BLOCK_STATUS, args))

            if SqliteStorageDriver._block_exists(res, check_status) is False:
                results.append(block_id)

        return results

    def create_block_generator(self, vault_id, marker=None,
            limit=None):

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'limit': self._determine_limit(limit),
            'marker': self._determine_marker(marker)
        }

        res = self._conn.execute(SQL_GET_ALL_BLOCKS, args)

        return [row[0] for row in res]

    def create_file_generator(self, vault_id,
                              marker=None, limit=None, finalized=True):

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'limit': self._determine_limit(limit),
            'marker': self._determine_marker(marker),
            'finalized': finalized
        }

        res = self._conn.execute(SQL_GET_ALL_FILES, args)
        return [row[0] for row in res]

    def create_file_block_generator(self, vault_id, file_id,
                                    offset=None, limit=None):

        args = {
            'fileid': file_id,
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
        }

        if limit is None:
            query = SQL_GET_ALL_FILE_BLOCKS

        else:
            query = SQL_GET_FILE_BLOCKS

            args.update({
                'limit': self._determine_limit(limit),
                'offset': offset or 0
            })

        query_res = self._conn.execute(query, args)

        return [(row[0], row[1]) for row in query_res]

    def assign_block(self, vault_id, file_id, block_id, offset):
        # TODO(jdp): tweak this to support multiple assignments
        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'fileid': file_id,
            'blockid': block_id,
            'offset': offset
        }

        self._conn.execute(SQL_ASSIGN_BLOCK_TO_FILE, args)

        del args['fileid']
        del args['offset']
        self._conn.execute(SQL_UPDATE_REF_TIME, args)

        self._conn.commit()

    def assign_blocks(self, vault_id, file_id, block_ids, offsets):
        # TODO(jdp): tweak this to support multiple assignments

        for block_id, offset in zip(block_ids, offsets):
            args = {
                'projectid': deuce.context.project_id,
                'vaultid': vault_id,
                'fileid': file_id,
                'blockid': block_id,
                'offset': offset
            }

            self._conn.execute(SQL_ASSIGN_BLOCK_TO_FILE, args)

            del args['fileid']
            del args['offset']
            self._conn.execute(SQL_UPDATE_REF_TIME, args)

            self._conn.commit()

    def register_block(self, vault_id, block_id, storage_id, blocksize):
        if not self.has_block(vault_id, block_id, check_status=True):
            args = {
                'projectid': deuce.context.project_id,
                'vaultid': vault_id,
                'blockid': block_id,
                'blocksize': int(blocksize),
                'storageid': storage_id
            }

            self._conn.execute(SQL_REGISTER_BLOCK, args)
            self._conn.commit()

    def unregister_block(self, vault_id, block_id):

        self._require_no_block_refs(vault_id, block_id)

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        self._conn.execute(SQL_UNREGISTER_BLOCK, args)
        self._conn.commit()

    def get_block_ref_count(self, vault_id, block_id):

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        query_res = self._conn.execute(SQL_GET_BLOCK_REF_COUNT, args)

        count = next(query_res)[0]

        return count if not None else 0

    def get_block_ref_modified(self, vault_id, block_id):

        args = {
            'projectid': deuce.context.project_id,
            'vaultid': vault_id,
            'blockid': block_id
        }

        query_res = self._conn.execute(SQL_GET_REF_TIME, args)

        try:
            return next(query_res)[0]
        except:
            return 0

    def get_health(self):
        try:
            # TODO: Collect more system statistics.
            return ["sqlite is active."]
        except:  # pragma: no cover
            return ["sqlite is not active."]
