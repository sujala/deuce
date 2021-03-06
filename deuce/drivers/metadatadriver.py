
import six
from abc import ABCMeta, abstractmethod, abstractproperty

# Note: calling NotImplementedError in each abstract method
# is to enable 100% code coverage when testing

import deuce
from deuce import conf


class OverlapError(Exception):
    """OverlapError is raised when finalizing
    a file is attempted but is not possible
    because two blocks overlap each other in
    the file"""
    def __init__(self, project_id, vault_id, file_id, block_id,
            startpos, endpos):
        """Creates a new OverlapError Exception

        :param vault_id: The vault containing the file
        :param file_id: The file containing the overlap
        :param block_id: The ID of the overlapping block
        :param startpos: The first overlapped byte
        :param endpos: The last overlapped block
        """
        self.project_id = project_id
        self.vault_id = vault_id
        self.file_id = file_id
        self.block_id = block_id
        self.startpos = startpos
        self.endpos = endpos

        msg = "[{0}/{1}] Overlap at block {2} file {3} at [{4}-{5}]".format(
            project_id, vault_id, block_id, file_id, startpos, endpos)

        Exception.__init__(self, msg)


class GapError(Exception):
    """GapError is raised becasue a file can
    not be finalized because a portion of the
    file is not covered by a block"""
    def __init__(self, project_id, vault_id, file_id, startpos, endpos):
        """Creates a new OverlapError Exception

        :param vault_id: The vault containing the file
        :param file_id: The file containing the overlap
        :param startpos: The first position of the detected gap
        :param endpos: The last position of the detected gap
        """
        self.project_id = project_id
        self.vault_id = vault_id
        self.file_id = file_id
        self.startpos = startpos
        self.endpos = endpos

        msg = "[{3}\{4}] Gap in file {0} from {1}-{2}".format(
            file_id, startpos, endpos, project_id, vault_id)

        Exception.__init__(self, msg)


class ConstraintError(Exception):
    """This exception is raised whenever there is
    an attempt to perform an operation that would
    otherwise be forbidden. This is roughly synonymous
    with things like SQL unique constraint errors, where
    the operation fails due to the fact that the
    schema restrictions would be violated.

    An example of where this exception should be thrown
    is when trying to delete a block that has files
    referring to it"""
    def __init__(self, project_id, vault_id, msg):
        """Creates a new InvalidOperationError Exception

        :param vault_id: The ID of the vault on which
                         operation was performed
        :param msg: A message describing the reason
        for the exception
        """
        self.project_id = project_id
        self.vault_id = vault_id

        Exception.__init__(self, msg)


@six.add_metaclass(ABCMeta)
class MetadataStorageDriver(object):
    """MetadataStorageDriver is an abstract base class that
    defines all functions necessary for a Deuce metadata
    driver.
    """

    @abstractmethod
    def create_vaults_generator(self, marker=None, limit=None):
        """Creates and returns a generator that will return
        the vault IDs.

        :param marker: The vault_id to start of the list
        :param limit: Number of returned items
        """
        raise NotImplementedError

    @abstractmethod
    def create_vault(self, vault_id):
        """Creates a representation of a vault.

        :param vault_id: The ID of the vault to create
        """
        raise NotImplementedError

    @abstractmethod
    def delete_vault(self, vault_id):
        """Deletes the vault from metadata.

        :param vault_id: The ID of the vault to delete
        """
        raise NotImplementedError

    @abstractmethod
    def get_vault_statistics(self, vault_id):
        """Return the statistics on the vault.

        :param vault_id: The ID of the vault to gather statistics for
        """
        raise NotImplementedError

    @abstractmethod
    def vault_health(self, vault_id):
        """Return the aggregate number of bad blocks and bad files
        contained within the vault
        :param vault_id: The ID of vault
        """
        raise NotImplementedError

    @abstractmethod
    def create_file(self, vault_id, file_id):
        """Creates a representation of an empty file."""
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, vault_id, file_id):
        """Deletes the file from storage."""
        raise NotImplementedError

    @abstractmethod
    def file_length(self, vault_id, file_id):
        """Retrieve length the of the file."""
        raise NotImplementedError

    @abstractmethod
    def has_file(self, vault_id, file_id):
        """Determines if the specified file exists in the vault."""
        raise NotImplementedError

    @abstractmethod
    def get_file_data(self, vault_id, file_id):
        """Returns a tule representing data for this file"""
        raise NotImplementedError

    @abstractmethod
    def finalize_file(self, vault_id, file_id, file_size=None):
        """Finalizes a file that has been de-duped. This
        check ensures that all blocks have been marked have
        been uploaded and that there are no 'gaps' in the
        metadata that comprise the file."""
        raise NotImplementedError

    @abstractmethod
    def is_finalized(self, vault_id, file_id):
        """Determines if this file has been finalized"""
        raise NotImplementedError

    @abstractmethod
    def create_block_generator(self, vault_id,
            marker=None, limit=None):
        """Creates and returns a generator that will return
        the ID of each block file. The file must previously
        have been finalized."""
        raise NotImplementedError

    @abstractmethod
    def create_file_generator(self, vault_id,
            marker=None, limit=None, finalized=True):
        """Creates and returns a generator that will return
        the ID of each block file. The file must previously
        have been finalized."""
        raise NotImplementedError

    @abstractmethod
    def create_file_block_generator(self, vault_id, file_id,
            offset=None, limit=None):
        """Creates and returns a generator that will return
        the ID of each block contained in the specified
        file. The file must previously have been finalized."""
        raise NotImplementedError

    @abstractmethod
    def mark_block_as_bad(self, vault_id, block_id):
        """Marks the block in the metadata driver as being a bad
        block."""
        raise NotImplementedError

    @abstractmethod
    def reset_block_status(self, vault_id, marker=None,
                           limit=None):
        """Marks the blocks for a given vault in the metadata driver
        as good blocks."""
        raise NotImplementedError

    @abstractmethod
    def has_block(self, vault_id, block_id, check_status=False):
        """Determines if the vault has the specified block.

        :param vault_id: The vault to check for the block
        :param block_id: The ID of the block to check for
        :param check_status: Determines whether or not to determine
            the status of the block. If True, and the block was
            previously marked as being 'bad', this function will
            return False. If check_status is False, the status
            of the block is not considered at all"""
        raise NotImplementedError

    @abstractmethod
    def has_blocks(self, vault_id, block_ids, check_status=False):
        """Determines if the vault has the specified blocks and
        returns the missing blocks

        :param vault_id: ID of the vault
        :param block_ids: list of block_id
        :param check_status: Whether or not to consider the status
           of the block. See parameter ``check_status`` in
           function ``has_block`` for explanation.
        :returns: list of missing blocks ids"""
        raise NotImplementedError

    @abstractmethod
    def assign_block(self, vault_id, file_id, block_id, offset):
        """Assigns the specified block to a particular offset in
        the file. No check is performed as to whether or not the
        block overlaps (it can't be done since a block that doesn't
        yet exist in storage can be assigned to a file).

        :param vault_id: The vault containing the file
        :param file_id: The ID of the file
        :param block_id: The ID of the block being assigned to the file
        :param offset: The position of the block in"""
        raise NotImplementedError

    @abstractmethod
    def assign_blocks(self, vault_id, file_id, block_ids, offsets):
        """Assigns the specified blocks to a particular offsets in
        the file. No check is performed as to whether or not the
        blocks overlap (it can't be done since a block that doesn't
        yet exist in storage can be assigned to a file).

        :param vault_id: The vault containing the file
        :param file_id: The ID of the file
        :param block_ids: The IDs of the blocks being assigned to the file
        :param offsets: The positions of the blocks"""
        raise NotImplementedError

    @abstractmethod
    def register_block(self, vault_id, block_id, storage_id, size):
        """Registers a block in the metadata driver."""
        raise NotImplementedError

    @abstractmethod
    def get_block_storage_id(self, vault_id, block_id):
        """Retrieve storage id for a given block id"""
        raise NotImplementedError

    @abstractmethod
    def get_block_metadata_id(self, vault_id, storage_id):
        """Retrieve block id for a given storage id"""
        raise NotImplementedError

    @abstractmethod
    def get_block_data(self, vault_id, block_id):  # TODO: rename
        """Returns the size of the block"""
        raise NotImplementedError

    @abstractmethod
    def unregister_block(self, vault_id, block_id):
        """Unregisters (removes) the block from the metadata
        store"""
        raise NotImplementedError

    @abstractmethod
    def get_block_ref_count(self, vault_id, block_id):
        """Returns an integer indicating the number of referencs
        to the specified block. Note that each reference of the
        block is counted, even if from the same file. If the
        block does not exist, None shall be returned.

        :param vault_id: The ID of the vault containing the block
        :param block_id: The ID the block to check references on
        """
        raise NotImplementedError

    @abstractmethod
    def get_block_ref_modified(self, vault_id, block_id):
        """Returns the UNIX epoch in UTC indicating the time that the
        block reference data was last modified.

        :param vault_id: The ID of the vault containing the block
        :param block_id: The ID the block to check references on
        """
        raise NotImplementedError

    @abstractmethod
    def get_health(self):
        """Check the meta driver health status"""
        raise NotImplementedError

    def _require_no_block_refs(self, vault_id, block_id):
        """This function checks the number of block references and
        requires that there be none. If there are block references,
        this function raise an InvalidOperationError exception"""

        if self.get_block_ref_count(vault_id, block_id) > 0:
            raise ConstraintError(
                deuce.context.project_id,
                vault_id,
                "Constraint Error: Block {0} has references".format(block_id)
            )

    def _determine_limit(self, limit):
        """ Determines the limit based on user input """

        res = conf.api_configuration.default_returned_num if not \
            limit else min(conf.api_configuration.max_returned_num, limit)

        return res
