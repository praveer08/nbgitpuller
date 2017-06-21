import os
import re
import subprocess
from .util import logger


class GitAutoSync:
    DELETED_FILE_REGEX = re.compile(
        r"deleted:\s+"  # Look for deleted: + any amount of whitespace...
        r"([^\n\r]+)"   # and match the filename afterward.
    )

    _git_url = ''
    _branch_name = ''
    _repo_dir = ''
    _cwd = ''

    def __init__(self, git_url, branch_name, repo_dir):
        assert git_url and branch_name

        self._git_url = git_url
        self._branch_name = branch_name
        self._repo_dir = repo_dir
        self._cwd = self._get_sub_cwd()

    def pull_from_remote(self):
        """
        Pull selected repo from a remote git repository,
        while preserving user changes
        """

        logger.info('Pulling into {} from {}, branch {}'.format(
            self._repo_dir,
            self._git_url,
            self._branch_name
        ))

        if not os.path.exists(self._repo_dir):
            self._initialize_repo()
        else:
            self._update_repo()

        logger.info('Pulled from repo: {}'.format(self._git_url))

    def _initialize_repo(self):
        """
        Clones repository.
        """

        logger.info('Repo {} doesn\'t exist. Cloning...'.format(self._repo_dir))
        subprocess.check_call(['git', 'clone', self._git_url, self._repo_dir])
        logger.info('Repo {} initialized'.format(self._repo_dir))

    def _update_repo(self):
        """
        Update repo by merging local and upstream changes
        """

        self._reset_deleted_files()
        if self._repo_is_dirty():
            self._make_commit()
        self._pull_and_resolve_conflicts()

    def _reset_deleted_files(self):
        """
        Runs the equivalent of git checkout -- <file> for each file that was
        deleted. This allows us to delete a file, hit an interact link, then get a
        clean version of the file again.
        """

        status = subprocess.check_output(['git', 'status'], cwd=self._cwd)
        deleted_files = self.DELETED_FILE_REGEX.findall(status.decode('utf-8'))

        for filename in deleted_files:
            subprocess.check_call(['git', 'checkout', '--', self._clean_path(filename)], cwd=self._cwd)
            logger.info('Resetted {}'.format(filename))

    def _make_commit(self):
        """
        Commit local changes
        """

        subprocess.check_call(['git', 'checkout', self._branch_name], cwd=self._cwd)
        subprocess.check_call(['git', 'add', '-A'], cwd=self._cwd)
        subprocess.check_call(['git', 'config', 'user.email', '"gitautopull@email.com"'], cwd=self._cwd)
        subprocess.check_call(['git', 'config', 'user.name', '"GitAutoPull"'], cwd=self._cwd)
        subprocess.check_call(['git', 'commit', '-m', 'WIP'], cwd=self._cwd)
        logger.info('Made WIP commit')

    def _pull_and_resolve_conflicts(self):
        """
        Git pulls, resolving conflicts with -Xours
        """

        logger.info('Starting pull from {}'.format(self._git_url))

        subprocess.check_call(['git', 'checkout', self._branch_name], cwd=self._cwd)
        subprocess.check_call(['git', 'fetch'], cwd=self._cwd)
        subprocess.check_call(['git', 'merge', '-Xours', 'origin/{}'.format(self._branch_name)], cwd=self._cwd)

        logger.info('Pulled from {}'.format(self._git_url))

    def _repo_is_dirty(self):
        """
        Return empty string if repo not dirty.
        Return non-empty string if repo dirty.
        """
        p = subprocess.Popen('git diff-index --name-status HEAD -- | grep -e "^M.*$"',
                             stdout=subprocess.PIPE, cwd=self._cwd, shell=True)
        p.wait()
        out, err = p.communicate()

        return out

    def _get_sub_cwd(self):
        """
        Get sub dir name from current workind directory
        """
        return '{}/{}'.format(os.getcwd(), self._repo_dir)

    def _clean_path(self, path):
        """
        Clean filename so that it is command line friendly.
        Currently just escapes spaces.
        """
        return path.replace(' ', '\ ')
