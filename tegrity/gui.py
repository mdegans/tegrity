import abc
import collections
import os
import functools
import json

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import logging
logger = logging.getLogger(__name__)
log_buffer = Gtk.TextBuffer()

THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)

from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)
Config = Mapping[str, Mapping[str, Any]]

import tegrity


class TextBufferLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        log_buffer.insert(
            log_buffer.get_end_iter(),
            f"{self.format(record)}\n")


class Page(abc.ABC):
    # this should match the page's name in glade:
    NAME = None
    # this saves typing in the kwargs getter and setter
    # an attribute must exist on self for each item in this iterable:
    SETTABLE_KWARGS = tuple()
    # this is necessary since Glade is not saving the property in XML for
    # some reason, set to try to add padding around self.content
    HAS_PADDING = False

    def __init__(self, builder: Gtk.Builder):
        # the root widget for the page
        self.builder = builder
        self.content = builder.get_object(self.NAME)  # type: Gtk.Widget
        self.switch = builder.get_object(
            f'{self.NAME}_switch')  # type: Optional[Gtk.Switch]
        if self.switch is not None:
            self.switch.connect('state-set', self.on_page_switch_state_set)
        if self.HAS_PADDING:
            builder.wiz.set_page_has_padding(self.content, True)

    # Callbacks

    def on_page_switch_state_set(self, *_, **__):
        """called on self.switch state-set signal"""
        logger.debug(
            f'{self.__class__.__name__}.on_page_switch_state_set() '
            f'not implemented')

    def on_prepare(self, wiz: Gtk.Assistant, page: Gtk.Widget, *_, **__):
        """called on prepare signal for the page"""
        logger.debug(
            f'{self.__class__.__name__}.on_prepare() not implemented')

    def error_dialog(self, err: Exception, *_, title: str = None, **__):
        error_dialog(self.builder.wiz, err, title=title)

    # Properties

    @property
    def on(self) -> bool:
        if self.switch is not None:
            return self.switch.get_active()
        return True

    @on.setter
    def on(self, active: bool):
        if self.switch is not None:
            self.switch.set_active(active)

    @property
    def kwargs(self) -> Optional[Dict]:
        if self.on:
            return {k: getattr(self, k) for k in self.SETTABLE_KWARGS}
            # todo: debate adding if getattr(self, k) to strip None and False
            #  values... adding the empty values may make it easier for people
            #  to customize the config with a text editor... or i could supply
            #  a sample config with all the options

    @kwargs.setter
    def kwargs(self, kwargs: Optional[Mapping]):
        if kwargs:
            for k, v in kwargs.items():
                if k in self.SETTABLE_KWARGS:
                    try:
                        setattr(self, k, v)
                        self.on = True
                    except Exception as err:
                        self.error_dialog(err, title=f'"{v}" not a valid {k}')
                else:
                    logger.warning(f"{k} not in SETTABLE_KWARGS")
        else:
            self.on = False

    def show(self, *_, **__):
        self.content.show()

    def hide(self, *_, **__):
        self.content.hide()

    def complete(self, *_, **__):
        self.builder.wiz.set_page_complete(self.content, True)


class JetPackPage(Page):

    NAME = 'page_jetpack'

    # stores a bundle row from sdkm.db
    bundle = None

    def __init__(self, builder: Gtk.Builder):
        super().__init__(builder)
        self.chooser = builder.get_object(
            'jetpack_chooser')  # type: Gtk.ComboBoxText
        self.chooser.connect('changed', self.on_jetpack_chooser_changed)
        self.details = builder.get_object(
            'jetpack_details')  # type: Gtk.TextView

        # set up jetpack page:
        self.chooser = builder.get_object('jetpack_chooser')  # type: Gtk.ComboBoxText
        try:
            with tegrity.db.connect() as conn:
                self.bundles = tegrity.db.get_bundles(conn)
            for bundle in self.bundles:
                self.chooser.append_text(tegrity.db.bundle_formatter(bundle))
        except Exception as err:
            self.error_dialog(err)
        self.details = builder.get_object('jetpack_details')  # type: Gtk.TextView
        self.details_buffer = Gtk.TextBuffer()
        self.details.set_buffer(self.details_buffer)

    # Callbacks:

    # todo: figure out a way to move this into JetPackPAge
    def on_jetpack_chooser_changed(self, *_, **__):
        idx = self.chooser.get_active()
        if id != -1:
            bundle = self.bundles[idx]
            self.bundle = bundle
            logger.debug(
                f'bundle selected: {tegrity.db.bundle_formatter(bundle)}')
            self.builder.l4t_path = tegrity.db.get_l4t_path(bundle)
            text = f"""Details from ~/.nvsdkm/sdkm.db
            Linux_for_Tegra path = {self.builder.l4t_path}
            rootfs path = {self.builder.rootfs_page.rootfs}
            """
            self.details_buffer.set_text(text)
            self.complete()


class KernelPage(Page):

    NAME = 'page_kernel'
    SETTABLE_KWARGS = (
        'cross_prefix',
        'public_sources',
        'public_sources_sha512',
        'localversion',
        'save_kconfig',
        'load_kconfig',
        'gconfig',
    )
    HAS_PADDING = True

    def __init__(self, builder: Gtk.Builder, kwargs=None):
        super().__init__(builder)

        self.options_grid = builder.get_object(
            'kernel_options_grid')  # type: Gtk.Grid
        self.cross_prefix_chooser = builder.get_object(
            'cross_prefix_chooser')  # type: Gtk.ComboBoxText
        self.public_sources_chooser = builder.get_object(
            'public_sources_chooser')  # type: Gtk.ComboBoxText
        self.public_sources_sha_entry = builder.get_object(
            'public_sources_sha_entry')  # type: Gtk.Entry
        self.localversion_entry = builder.get_object(
            'localversion_entry')  # type: Gtk.Entry
        self.save_kconfig_file_chooser = builder.get_object(
            'save_kconfig_file_chooser')  # type: Gtk.FileChooser
        self.load_kconfig_file_chooser = builder.get_object(
            'load_kconfig_file_chooser')  # type: Gtk.FileChooser
        self.gconfig_switch = builder.get_object(
            'gconfig_switch')  # type: Gtk.Switch

        # init with supplied properties
        self.kwargs = kwargs

        # add some defaults to dropdowns:

        # add the autodetected cross prefix if any
        autodetected_cross = tegrity.toolchain.get_cross_prefix()
        if self.cross_prefix != autodetected_cross:
            self.cross_prefix = autodetected_cross
        # add the public source tarball if none supplied
        if not self.public_sources:
            self.public_sources = tegrity.kernel.NANO_TX1_KERNEL_URL
            self.public_sources_sha512 = tegrity.kernel.NANO_TX1_KERNEL_SHA512
        # todo: figure out why combo box text not editable
        if not self.localversion:
            self.localversion = tegrity.kernel.DEFAULT_LOCALVERSION

    # Callbacks

    def on_page_switch_state_set(self, *_, **__):
        self.options_grid.set_visible(self.on)

    # Properties (must set and get all in SETTABLE_KWARGS)

    @property
    def cross_prefix(self) -> str:
        return self.cross_prefix_chooser.get_active_text()

    @cross_prefix.setter
    def cross_prefix(self, path: str):
        tegrity.toolchain.validate_cross_prefix(path)
        self.cross_prefix_chooser.append_text(path)
        self.cross_prefix_chooser.set_active(0)
        # todo: also set active to la

    @property
    def public_sources(self) -> str:
        txt = self.public_sources_chooser.get_active_text()
        if txt:
            return txt

    @public_sources.setter
    def public_sources(self, url_or_path: str):
        tegrity.kernel.validate_public_sources(url_or_path)
        self.public_sources_chooser.append_text(url_or_path)
        self.public_sources_chooser.set_active(0)

    @property
    def public_sources_sha512(self):
        txt = self.public_sources_sha_entry.get_text()
        if txt:
            return txt

    @public_sources_sha512.setter
    def public_sources_sha512(self, sha512: str):
        tegrity.kernel.validate_public_sources_sha512(sha512)
        self.public_sources_sha_entry.set_text(sha512)

    @property
    def localversion(self) -> str:
        return self.localversion_entry.get_text()

    @localversion.setter
    def localversion(self, suffix: str):
        self. localversion_entry.set_text(suffix)

    @property
    def save_kconfig(self) -> str:
        return self.save_kconfig_file_chooser.get_filename()

    @save_kconfig.setter
    def save_kconfig(self, filename: str):
        tegrity.kernel.validate_save_config(filename)
        self.save_kconfig_file_chooser.set_filename(filename)

    @property
    def load_kconfig(self) -> str:
        return self.load_kconfig_file_chooser.get_filename()

    @load_kconfig.setter
    def load_kconfig(self, filename: str):
        tegrity.kernel.validate_load_kconfig(filename)
        self.load_kconfig_file_chooser.set_filename(filename)

    @property
    def gconfig(self) -> bool:
        return self.gconfig_switch.get_active()

    @gconfig.setter
    def gconfig(self, active: bool):
        self.gconfig_switch.set_active(active)


class RootfsPage(Page):
    NAME = 'page_rootfs'
    SETTABLE_KWARGS = (
        'rootfs',
        'source',
        'source_sha512',
    )
    HAS_PADDING = True

    def __init__(self, builder: Gtk.Builder, kwargs=None):
        super().__init__(builder)
        self.kwargs = kwargs

        # set up rootfs page:
        self.path_chooser = builder.get_object(
            'rootfs_path_chooser')  # type: Gtk.FileChooserButton
        self.path_chooser.connect('file-set', self.complete)
        self.ota_updates_switch = builder.get_object(
            'ota_updates_switch')  # type: Gtk.Switch
        self.apt_upgrade_switch = builder.get_object(
            'apt_upgrade_switch')  # type: Gtk.Switch
        self.reset_switch = builder.get_object(
            'rootfs_reset_switch')  # type: Gtk.Switch
        self.reset_switch.connect(
            'state-set', self.on_rootfs_reset_switch_toggled)
        self.source_grid = builder.get_object(
            'rootfs_source_grid')  # type: Gtk.Grid
        self.source_path_chooser = builder.get_object(
            'rootfs_source_path_chooser')  # type: Gtk.ComboBoxText
        self.sha_entry = builder.get_object(
            'rootfs_sha_entry')  # type: Gtk.Entry
        self.source = tegrity.rootfs.L4T_ROOTFS_URL
        self.source_sha512 = tegrity.rootfs.L4T_ROOTFS_SHA512

    # Callbacks:

    def on_rootfs_reset_switch_toggled(self, *_, **__):
        self.source_grid.set_visible(self.rootfs_reset)

    # Properties:

    @property
    def apt_upgrade(self) -> bool:
        return self.apt_upgrade_switch.get_active()

    @apt_upgrade.setter
    def apt_upgrade(self, active: bool):
        self.apt_upgrade_switch.set_active(active)

    @property
    def rootfs_reset(self) -> bool:
        return self.reset_switch.get_active()

    @rootfs_reset.setter
    def rootfs_reset(self, active: bool):
        self.reset_switch.set_active(active)

    @property
    def rootfs(self) -> str:
        return self.path_chooser.get_filename()

    @rootfs.setter
    def rootfs(self, filename: str):
        self.path_chooser.set_filename(filename)
        self.complete()

    @property
    def source(self) -> str:
        return self.source_path_chooser.get_active_text()

    @source.setter
    def source(self, path: str):
        self.source_path_chooser.append_text(path)
        self.source_path_chooser.set_active(0)

    @property
    def source_sha512(self) -> str:
        return self.sha_entry.get_text()

    @source_sha512.setter
    def source_sha512(self, sha512: str):
        # todo: move this validation function somewhere other than tegrity.kernel
        tegrity.kernel.validate_public_sources_sha512(sha512)
        self.sha_entry.set_text(sha512)

    # todo: rename tegrity.rootfs.main fix_sources parameter

    @property
    def fix_sources(self) -> bool:
        return self.ota_updates_switch.get_active()

    @fix_sources.setter
    def fix_sources(self, active: bool):
        self.ota_updates_switch.set_active(active)


class SoftwarePage(Page):

    NAME = 'page_software'
    SETTABLE_KWARGS = (
        'apt_kwargs',
    )

    proot = True
    update_complete = False

    def __init__(self, builder: Gtk.Builder):
        super().__init__(builder)

        # widgets:
        self.apt_refresh_button = builder.get_object(
            'apt_refresh_button')  # type: Gtk.Button
        self.apt_refresh_button.connect(
            'clicked', self.on_apt_refresh_clicked)
        self.apt_install_search_box = builder.get_object(
            'apt_install_search_box')  # type: Gtk.SearchEntry
        self.apt_install_search_box.connect(
            'activate', self.add_entry_to_text)
        self.apt_no_install_recommends_switch = builder.get_object(
            'apt_no_install_recommends_switch')  # type: Gtk.Switch
        self.apt_autoremove_switch = builder.get_object(
            'apt_autoremove_switch')  # type: Gtk.Switch
        self.apt_clean_switch = builder.get_object(
            'apt_clean_switch')  # type: Gtk.Switch
        self.apt_entry_completion = builder.get_object(
            'apt_entry_completion')  # type: Gtk.EntryCompletion
        self.apt_entry_completion.connect(
            'match-selected', self.add_entry_to_text)
        self.apt_install_text_view = builder.get_object(
            'apt_install_text_view')  # type: Gtk.TextView
        self.apt_validate_button = builder.get_object(
            'apt_validate_button')  # type: Gtk.Button
        self.apt_validate_button.connect(
            'clicked', self.apt_validate)
        self.apt_sort_button = builder.get_object(
            'apt_sort_button')  # type: Gtk.Button
        self.apt_sort_button.connect(
            'clicked', self.apt_sort)

        # data:
        self._package_text_buffer = Gtk.TextBuffer()
        self.apt_install_text_view.set_buffer(self._package_text_buffer)
        self._packages_available = Gtk.ListStore(str)
        self.apt_entry_completion.set_model(self._packages_available)
        self._packages_installed = Gtk.ListStore(str)

    # Callbacks

    def on_apt_refresh_clicked(self, *_, **__):
        if not self.update_complete:
            self.apt_update()
            self.update_complete = True
            self.apt_refresh_button.set_sensitive(False)

    def add_entry_to_text(self, *_, **__):
        package = self.apt_install_search_box.get_text()
        self.apt_install_search_box.set_text('')
        self._package_text_buffer.insert(
            self._package_text_buffer.get_end_iter(),
            f'\n{package}')

    def apt_validate(self, *_, **__):
        if not self.update_complete:
            logger.debug("need to apt update to validate config")
            self.on_apt_refresh_clicked()
        available = set(self.packages_available)
        pending = set(self.packages_pending)
        not_found = sorted(pending - available)
        if not_found:
            warning_dialog(
                self.builder.wiz, f'packages not found: {" ".join(not_found)}')
        logger.debug(f'apt_kwargs: {self.apt_kwargs}')
        logger.debug(f'kwargs: {self.kwargs}')

    def apt_update(self, *_, **__):
        # todo: only do the fix sources and apt update if not already done
        #  since apt update can take a minute or so
        if self.builder.rootfs_page.fix_sources:
            try:
                tegrity.apt.enable_nvidia_ota(self.builder.rootfs_page.rootfs)
                # todo: allow toggling both ways after update
                self.builder.rootfs_page.ota_updates_switch.set_sensitive(False)
            except Exception as err:
                self.error_dialog(err)
                return
        with tegrity.qemu.ProotRunner(self.builder.rootfs_page.rootfs) as runner:
            try:
                tegrity.apt.update(runner=runner)
                for package in tegrity.apt.list_(runner=runner, sorted_=True):
                    self._packages_available.append((package,))
                for package in tegrity.apt.list_installed(runner=runner, sorted_=True):
                    self._packages_installed.append((package,))
            except Exception as err:
                self.error_dialog(err)

    def apt_sort(self, *_, **__):
        self.packages_pending = self.packages_pending

    # Properties

    @property
    def packages_pending(self):
        return self._package_text_buffer.get_text(
            self._package_text_buffer.get_start_iter(),
            self._package_text_buffer.get_end_iter(),
            False
        ).split()

    @packages_pending.setter
    def packages_pending(self, packages: Iterable):
        self._package_text_buffer.set_text('\n'.join(sorted(set(packages))))

    @property
    def packages_available(self):
        return [row[0] for row in self._packages_available]

    @property
    def packages_installed(self):
        return [row[0] for row in self._packages_installed]

    @property
    def no_install_recommends(self) -> bool:
        return self.apt_no_install_recommends_switch.get_active()

    @no_install_recommends.setter
    def no_install_recommends(self, active: bool):
        self.apt_no_install_recommends_switch.set_active(active)

    @property
    def apt_clean(self) -> bool:
        return self.apt_clean_switch.get_active()

    @apt_clean.setter
    def apt_clean(self, active: bool):
        self.apt_clean_switch.set_active(active)

    @property
    def apt_autoremove(self) -> bool:
        return self.apt_autoremove_switch.get_active()

    @apt_autoremove.setter
    def apt_autoremove(self, active: bool):
        self.apt_autoremove_switch.set_active(active)

    @property
    def apt_kwargs(self):
        # todo: move ota updates and apt upgrade switch to dependencies tab,
        #  remove 'fix sources' from rootfs script
        kwargs = {
            'rootfs': self.builder.rootfs_page.rootfs,
            'nvidia_ota': self.builder.rootfs_page.fix_sources,
            'proot': self.proot,
            'apt_upgrade': self.builder.rootfs_page.apt_upgrade,
            'no_install_recommends': self.no_install_recommends,
            'apt_clean': self.apt_clean,
            'apt_autoremove': self.apt_autoremove,
        }
        pending = self.packages_pending
        if pending:
            kwargs.update({'apt_install': sorted(pending)})
        return kwargs

    @apt_kwargs.setter
    def apt_kwargs(self, kwargs: Mapping[str, Any]):
        if 'nvidia_ota' in kwargs:
            self.builder.rootfs_page.fix_sources = kwargs['nvidia_ota']
        if 'apt_upgrade' in kwargs:
            self.builder.rootfs_page.apt_upgrade = kwargs['apt_upgrade']
        if 'apt_install' in kwargs:
            self.packages_pending = kwargs['apt_install']
        # for now, proot should probably always be true
        # if 'proot' in kwargs:
        #     self.proot = kwargs['proot']
        if 'no_install_recommends' in kwargs:
            self.no_install_recommends = kwargs['no_install_recommends']
        if 'apt_clean' in kwargs:
            self.apt_clean = kwargs['apt_clean']
        if 'autoremove_' in kwargs:
            self.apt_autoremove = kwargs['apt_autoremove']


# noinspection PyProtectedMember
class UsersPage(Page):

    NAME = 'page_users'

    # this is really dumb that this is necessary. the column headers should be
    # read from the xml by the builder

    def __init__(self, builder: Gtk.Builder,
                 list_of_kwargs: Iterable[Mapping[str, Any]] = None):
        super().__init__(builder)
        # set up simple adduser widgets
        self.username_entry = builder.get_object(
            'username_entry')  # type: Gtk.Entry
        self.username_entry.connect(
            'activate', self.add_user_from_entry)
        self.system_user_switch = builder.get_object(
            'system_user_switch')  # type: Gtk.Switch
        self.user_authorized_keys_text_view = builder.get_object(
            'user_authorized_keys_text_view')  # type: Gtk.TextView
        self.user_authorized_keys_buffer = Gtk.TextBuffer()
        self.user_authorized_keys_text_view.set_buffer(
            self.user_authorized_keys_buffer)
        self.add_user_button = builder.get_object(
            'add_user_button')  # type: Gtk.Button
        self.add_user_button.connect(
            'clicked', self.add_user_from_entry)

        # set up User row class
        self.User = collections.namedtuple(
            'User', (c.name for c in self.COLUMNS))
        # build the view
        self.tree_view = builder.get_object(
            'users_tree_view')  # type: Gtk.TreeView
        # build the internal list with the column types
        self.list_store = Gtk.ListStore(*(c.type for c in self.COLUMNS))
        # put the list in the view
        self.tree_view.set_model(self.list_store)
        # add columns to the view
        for i, column_info in enumerate(self.COLUMNS):
            if column_info.type is bool:
                renderer = Gtk.CellRendererToggle(activatable=True)
                toggled_cb = functools.partial(
                    self.on_bool_column_toggled, i)
                renderer.connect('toggled', toggled_cb)
                arguments = {'active': i}

            else:
                renderer = Gtk.CellRendererText(editable=True)
                edited_cb = functools.partial(
                    self.on_str_column_edited, i,
                    validator=column_info.validator)
                renderer.connect('edited', edited_cb)
                arguments = {'text': i}
            column = Gtk.TreeViewColumn(
                column_info.name, renderer, **arguments)
            column.set_expand(True)
            column.set_sort_column_id(i)
            self.tree_view.append_column(column)

        if list_of_kwargs:
            self.list_of_kwargs = list_of_kwargs

    # Callbacks:

    def on_str_column_edited(self,
                             colnum: int,
                             _: Gtk.CellRendererText,
                             rownum, new_text: str,
                             validator: Callable[[str], Any] = None):
        if validator:
            try:
                if colnum == 0:
                    validator(new_text, system=self.list_store[rownum][8])
                else:
                    validator(new_text)
            except Exception as err:
                self.error_dialog(err)
                return
        self.list_store[rownum][colnum] = new_text

    def on_bool_column_toggled(self,
                               colnum,
                               _: Gtk.CellRendererToggle,
                               rownum):
        self.list_store[rownum][colnum] = not self.list_store[rownum][colnum]
        try:
            self.validate_user(self.list_store[rownum], check_exists=False)
        except Exception as err:
            self.error_dialog(err)

    def add_user_from_entry(self, *_, **__):
        kwargs = {
            'name': self.username_entry.get_text(),
            'group': self.system_user_switch.get_active(),
            'authorized_keys': self.user_authorized_keys_buffer.get_text(
                self.user_authorized_keys_buffer.get_start_iter(),
                self.user_authorized_keys_buffer.get_end_iter(),
                False,
            ),
        }
        if self.system_user_switch.get_active():
            kwargs.update({'system': True})
        else:
            extra_groups = {
                'audio',
                'video',
                'i2c',
                'gdm',
                'gpio',
                'weston-launch',
            }
            first_user_extra_groups = {
                'adm',
                'audio',
                'cdrom',
                'dip',
                'gdm',
                'gpio',
                'i2c',
                'lpadmin',
                'plugdev',
                'sambashare',
                'sudo',
                'video',
                'weston-launch',
            }
            # noinspection PyUnresolvedReferences
            if not any(not user.system for user in self.rows):
                extra_groups |= first_user_extra_groups
            kwargs.update({'add_extra_groups': ' '.join(sorted(extra_groups))})
        self.add_user(**kwargs)
        self.username_entry.set_text('')
        self.user_authorized_keys_buffer.set_text('')

    def validate_shell(self, shell: str):
        """wraps tegrity.validators.validate_shell, adding rootfs kwarg"""
        tegrity.validators.validate_shell(
            shell, rootfs=self.builder.rootfs_page.rootfs)

    # noinspection PyUnresolvedReferences
    def validate_user(self, user: Union[NamedTuple, Tuple], check_exists=True):
        # todo: clean up, or remove system parameter on validate_username entirely
        #  since
        logger.debug(f'validating user row: {user}')
        fail = False
        try:
            if not isinstance(user, self.User):
                user = self.User(*user)
            tegrity.validators.validate_username(user.name, system=user.system)
        except Exception as err:
            fail = True
            self.error_dialog(err)
        if check_exists and user.name in (u.name for u in self.rows):
            # todo: check for existing users in /etc/passwd
            #  pwd module doesn't seem to support custom paths to this :(
            raise ValueError(f"username {user.name} already exists")
        for i, column_info in enumerate(self.COLUMNS):
            if column_info.validator:
                if column_info.required or user[i] != column_info.default:
                    try:
                        column_info.validator(user[i])
                    except Exception as err:
                        fail = True
                        self.error_dialog(err)
        if fail:
            raise ValueError(f"validation failed for user row: {user}")
        return user

    # Properties:

    ColumnInfo = collections.namedtuple(
        'ColumnInfo', ('name', 'required', 'default', 'type', 'validator'))

    # noinspection PyPep8Naming
    @property
    def COLUMNS(self):
        return (
            self.ColumnInfo('name', True, '', str, tegrity.validators.validate_username),
            self.ColumnInfo('gecos', False, '', str, tegrity.validators.validate_gecos),
            self.ColumnInfo('gid', False, '', str, tegrity.validators.validate_uid_gid),
            self.ColumnInfo('group', False, False, bool, None),
            self.ColumnInfo('home', False, '', str, tegrity.validators.validate_home),
            self.ColumnInfo('shell', False, '', str, self.validate_shell),
            self.ColumnInfo('ingroup', False, '', str, tegrity.validators.validate_ingroup),
            self.ColumnInfo('no_create_home', False, False, bool, None),
            self.ColumnInfo('system', False, False, bool, None),
            self.ColumnInfo('uid', False, '', str, tegrity.validators.validate_uid_gid),
            self.ColumnInfo('firstuid', False, '', str, tegrity.validators.validate_uid_gid),
            self.ColumnInfo('lastuid', False, '', str, tegrity.validators.validate_uid_gid),
            self.ColumnInfo('add_extra_groups', False, '', str, tegrity.validators.validate_add_extra_groups),
            self.ColumnInfo('authorized_keys', True, '', str, tegrity.validators.validate_authorized_keys),
        )

    @property
    def list_of_kwargs(self):
        lok = []
        for user in self.rows:
            # remove empty or false values:
            kwargs = {k: v for k, v in user._asdict().items() if v}
            lok.append(kwargs)
        return lok

    @list_of_kwargs.setter
    def list_of_kwargs(self, list_of_kwargs: Iterable[Mapping[str, Any]]):
        self.list_store.clear()
        for kwargs in list_of_kwargs:
            self.add_user(**kwargs)

    @property
    def rows(self) -> Optional[List[NamedTuple]]:
        # noinspection PyTypeChecker
        return [self.User(*row) for row in self.list_store]

    @rows.setter
    def rows(self, rows: Iterable[Union[Tuple, NamedTuple]]):
        self.list_store.clear()
        for user in rows:
            self.add_user(user)

    @property
    def kwargs(self) -> Optional[Dict]:
        raise NotImplemented(
            f'use {self.__class__.__name__}.list_of_kwargs instead')

    @kwargs.setter
    def kwargs(self, kwargs: Mapping):
        raise NotImplemented(
            f'use {self.__class__.__name__}.list_of_kwargs instead')

    def add_user(self, user: Union[Tuple, NamedTuple] = None, **kwargs):
        if kwargs:
            default_row = self.User(*(c.default for c in self.COLUMNS))
            row_data = default_row._asdict()
            row_data.update(kwargs)
            user = self.User(**row_data)
            return self.add_user(user)
        # make sure everything will fit in the row:
        try:
            self.list_store.append(self.validate_user(user))
        except Exception as err:
            self.error_dialog(err)


class SecurityPage(Page):

    NAME = 'page_security'


class StartupPage(Page):

    NAME = 'page_startup'


class ConfimPage(Page):

    NAME = 'page_confirm'

    SECTIONS = (
        'kernel',
        'rootfs',
        'software',
    )

    JSON_INDENT = 2

    def __init__(self, builder: Gtk.Builder):
        super().__init__(builder)
        self.text_view = builder.get_object(
            'confirm_text_view')  # type: Gtk.TextView
        self.json_switch = builder.get_object(
            'confirm_json_view_switch')  # type: Gtk.Switch
        self.json_switch.connect(
            'state-set', self.on_json_switch_set_state)
        self.plain_text_buffer = Gtk.TextBuffer()
        self.json_buffer = Gtk.TextBuffer()
        self.text_view.set_buffer(self.plain_text_buffer)

    # Callbacks

    def on_prepare(self, *_, **__):
        try:
            config = self.config
            self.json = config
            self.text = config
            self.complete()
        except Exception as err:
            self.error_dialog(err)
            return

    def on_json_switch_set_state(self, *_, **__):
        if self.json_switch.get_active():
            self.text_view.set_buffer(self.json_buffer)
        else:
            self.text_view.set_buffer(self.plain_text_buffer)

    # Properties

    @property
    def config(self) -> Config:
        config = dict()
        for title in self.SECTIONS:
            page = getattr(self.builder, f'{title}_page')
            kwargs = page.kwargs
            if kwargs is None:
                continue
            config.update({title: kwargs})
        return config

    @config.setter
    def config(self, config: Config):
        for page_title, kwargs in config.items():
            page = getattr(self.builder, f'{page_title}_page')
            page.kwargs = kwargs
        self.on_prepare()

    @property
    def json(self):
        return self.json_buffer.get_text()

    @json.setter
    def json(self, config: Mapping):
        self.json_buffer.set_text(json.dumps(config, indent=self.JSON_INDENT))

    @property
    def text(self):
        return self.plain_text_buffer.get_text()

    @text.setter
    def text(self, config: Mapping):
        sections = []
        for section_name, kwargs in config.items():
            if not kwargs:
                continue
            sections.append(f'{section_name}:')
            sections.append(
                '\n'.join(
                    [f'\t{k}={v}' for k, v in kwargs.items()]
                )
            )
        self.plain_text_buffer.set_text('\n'.join(sections))


def warning_dialog(parent: Gtk.Widget, message: str, *_, **__):
    logger.warning(message)
    dialog = Gtk.MessageDialog(parent=parent,
                               flags=Gtk.DialogFlags.MODAL,
                               # in case of 100 errors, better to be modal
                               # to the page, not the whole app
                               # todo: test this works
                               type=Gtk.MessageType.WARNING,
                               buttons=Gtk.ButtonsType.CLOSE,
                               message_format=message)
    dialog.set_title('warning')

    def close(*_, **__):
        dialog.close()

    dialog.connect('response', close)
    dialog.show()


def error_dialog(parent: Gtk.Widget, err: Exception, *_, title: str = None, **__):
    logger.error(err)
    dialog = Gtk.MessageDialog(parent=parent,
                               flags=Gtk.DialogFlags.MODAL,
                               # in case of 100 errors, better to be modal
                               # to the page, not the whole app
                               # todo: test this works
                               type=Gtk.MessageType.ERROR,
                               buttons=Gtk.ButtonsType.CLOSE,
                               message_format=f'{err.__class__.__name__}: {str(err)}')
    if title:
        dialog.set_title(title)
    else:
        dialog.set_title(err.__class__.__name__)

    def close(*_, **__):
        dialog.close()

    dialog.connect('response', close)
    dialog.show()


class WizardBuilder(Gtk.Builder):
    # the layout XML
    XML = os.path.join(THIS_DIR, 'wizard.glade')

    # these attributes are common to multiple pages / scripts
    # todo: make these properties with validation

    def __init__(self, l4t_path=None,
                 kernel_kwargs: Mapping = None,
                 rootfs_kwargs: Mapping = None,
                 users_list_of_kwargs: Iterable[Mapping] = None):
        # noinspection PyCallByClass
        Gtk.Builder.__init__(self)
        # common arguments to multiple pages:
        self._l4t_path = l4t_path

        # load XML
        self.add_from_file(self.XML)

        # load the main wizard
        self.wiz = self.get_object('tegrity_wizard')  # type: Gtk.Assistant
        self.connect_signals(
            {'not-implemented': functools.partial(
                warning_dialog, self.wiz, 'Not implemented yet.')})
        # for some reason the default signal is quit:
        self.wiz.connect('apply', self.on_apply)
        self.wiz.connect('prepare', self.on_prepare)
        self.wiz.connect('close', Gtk.main_quit)
        self.wiz.connect('cancel', Gtk.main_quit)

        # setup pages
        self.jetpack_page = JetPackPage(self)
        if l4t_path:  # manually specified, hide the JetPackPage
            self.jetpack_page.hide()
        self.kernel_page = KernelPage(self, kernel_kwargs)
        self.rootfs_page = RootfsPage(self, rootfs_kwargs)
        self.software_page = SoftwarePage(self)
        self.users_page = UsersPage(self, list_of_kwargs=users_list_of_kwargs)
        self.security_page = SecurityPage(self)
        self.startup_page = StartupPage(self)
        self.confirm_page = ConfimPage(self)

    # callbacks:

    def on_apply(self, *_, **__):
        # todo: actual apply logic, to run tegrity, refactor main tegrity script
        #  to accept a config file
        logger.debug('apply clicked, saving config to file.')
        logger.debug('running tegrity with config')

    def on_prepare(self, wiz: Gtk.Assistant, page: Gtk.Widget, *args, **kwargs):
        # todo: this is hacky. figure out a better way to do this
        #  if i wasn't creating Gtk objects from xml I would just subclass them
        #  and add my own functionality rather than using a wrapper like this
        #  if i could load classes from the builder that would work
        #  maybe i can reassign self in Page __init__ but when i tried that it
        #  didn't work, so for now this works. i might change the attribute names
        #  to be consistent KernelPage and page_kernel is confusing, for ex.
        title = wiz.get_page_title(page)
        if title is None:
            return
        title = title.lower()
        page = getattr(self, f'{title}_page')
        if page is None:
            return
        page.on_prepare(wiz, page, *args, **kwargs)

    # Properties to aggregate page kwargs with common kwargs, where necessary

    @property
    def l4t_path(self):
        return self._l4t_path

    @l4t_path.setter
    def l4t_path(self, path):
        self._l4t_path = path
        self.rootfs_page.rootfs = os.path.join(path, 'rootfs')

    # todo: remove these and any references to these, instead using just .config

    @property
    def kernel_kwargs(self) -> Mapping:
        kernel_kwargs = self.kernel_page.kwargs
        kernel_kwargs.update({'l4t_path': self.l4t_path})
        return kernel_kwargs

    @kernel_kwargs.setter
    def kernel_kwargs(self, kwargs: Mapping):
        kernel_kwargs = dict(kwargs)
        if 'l4t_path' in kernel_kwargs:
            self.l4t_path = kernel_kwargs['l4t_path']
            del kernel_kwargs['l4t_path']
        self.kernel_page.kwargs = kernel_kwargs

    @property
    def rootfs_kwargs(self) -> Mapping:
        return self.rootfs_page.kwargs

    @rootfs_kwargs.setter
    def rootfs_kwargs(self, kwargs: Mapping):
        self.rootfs_page.kwargs = kwargs

    @property
    def config(self) -> Config:
        return self.confirm_page.config

    @config.setter
    def config(self, config: Config):
        self.confirm_page.config = config


def cli_main():

    # todo: argparse boilerplate

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    gui_handler = TextBufferLogHandler()
    gui_handler.setLevel(logging.DEBUG)
    # noinspection PyArgumentList
    logging.basicConfig(level=logging.DEBUG, handlers=(ch, gui_handler))

    builder = WizardBuilder()

    builder.wiz.show()

    Gtk.main()


if __name__ == '__main__':
    import doctest
    doctest.testmod()
    cli_main()
