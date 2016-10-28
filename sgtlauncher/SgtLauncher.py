import gi
import os
import sys
import time

from locale import gettext as _

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gdk  # nopep8
from gi.repository import GdkPixbuf  # nopep8
from gi.repository import Gtk  # nopep8
from gi.repository import Gio  # nopep8
from gi.repository import GLib  # nopep8
from gi.repository import Pango  # nopep8

from . import SgtSocketLauncher  # nopep8


class MyWindow(Gtk.ApplicationWindow):
    def __init__(self, app, appname, settings, launchers):
        self.appname = appname
        self.title = _("SGT Puzzles Collection")

        Gtk.Window.__init__(self, title=self.title, application=app)
        self.set_title(self.title)
        self.set_role(self.title)
        self.set_startup_id("sgt-launcher")
        self.set_default_icon_name(appname)
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.launcher = SgtSocketLauncher.SgtSocketLauncher()
        self.loading = False
        self.load_id = 0
        self.load_retry = 0
        self.load_title = ""

        self.socket = self.launcher.get_socket()
        self.socket.connect("plug_removed", self.socket_disconnect)
        self.socket.connect("plug_added", self.socket_connect)

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        self.keyboard = seat.get_keyboard()

        self.setup_ui(launchers)

    def setup_ui(self, launchers):
        """Initialize the headerbar, actions, and individual views"""
        self.hb = Gtk.HeaderBar()
        self.hb.props.show_close_button = True
        self.hb.props.title = self.title
        self.set_titlebar(self.hb)

        self.stack = Gtk.Stack.new()
        self.add(self.stack)

        self.setup_action_buttons()
        self.setup_launcher_view(launchers)
        self.setup_loading_view()
        self.setup_game_view()

    def setup_action_buttons(self):
        """Initialize the in-game action buttons"""
        # Button definitions
        buttons = {
            "new-game": (_("New Game"), "document-new-symbolic", 57,
                         Gdk.KEY_n),
            "undo": (_("Undo"), "edit-undo-symbolic", 30, Gdk.KEY_u),
            "redo": (_("Redo"), "edit-redo-symbolic", 27, Gdk.KEY_r)
        }

        # Setup Action buttons
        self.action_buttons = {}
        for key in list(buttons.keys()):
            # Create the button
            self.action_buttons[key] = Gtk.Button.new_from_icon_name(
                buttons[key][1], Gtk.IconSize.LARGE_TOOLBAR)
            # Add a tooltip
            self.action_buttons[key].set_tooltip_text(buttons[key][0])
            # Enable hiding
            self.action_buttons[key].set_no_show_all(True)
            # Connect the clicked event
            self.action_buttons[key].connect("clicked",
                                             self.on_keyboard_button_click,
                                             buttons[key][2], buttons[key][3])

        # Add the buttons
        self.hb.pack_start(self.action_buttons["new-game"])

        buttonbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        ctx = buttonbox.get_style_context()
        ctx.add_class("linked")

        buttonbox.pack_start(self.action_buttons["undo"], False, False, 0)
        buttonbox.pack_start(self.action_buttons["redo"], False, False, 0)
        self.hb.pack_start(buttonbox)

    def setup_launcher_view(self, launchers):
        """Initialize the launcher view with the games"""
        # Populate the model (name, comment, icon_name, exe)
        listmodel = Gtk.ListStore(str, str, str, str)
        for launcher in launchers:
            listmodel.append(launcher)

        # Initialize the treeview
        view = Gtk.TreeView(model=listmodel)
        view.set_headers_visible(False)

        # Create and pack the custom column
        col = Gtk.TreeViewColumn.new()

        # Pixbuf: icon renderer
        pixbuf = Gtk.CellRendererPixbuf()
        pixbuf.props.stock_size = Gtk.IconSize.DIALOG
        col.pack_start(pixbuf, False)
        col.add_attribute(pixbuf, "icon-name", 2)

        # Text: label renderer
        text = Gtk.CellRendererText()
        text.props.wrap_mode = Pango.WrapMode.WORD
        col.pack_start(text, True)
        col.add_attribute(text, "text", 0)

        # Draw custom cell
        col.set_cell_data_func(text, self.treeview_cell_text_func, None)
        col.set_cell_data_func(pixbuf, self.treeview_cell_pixbuf_func, None)

        # Add the column and enable typeahead
        view.append_column(col)
        view.set_search_column(1)

        view.connect("row-activated", self.on_activated)

        # Add the treeview to a scrolled window
        scrolled = Gtk.ScrolledWindow.new()
        scrolled.add(view)

        self.stack.add_named(scrolled, "launcher")

    def setup_loading_view(self):
        """Initialize the loading view used to correctly embed the window"""
        parent_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        child_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)

        self.launching_image = Gtk.Image.new()
        self.launching_title = Gtk.Label.new()
        self.launching_label = Gtk.Label.new(_("Please wait..."))

        spinner = Gtk.Spinner.new()
        spinner.start()

        child_box.pack_start(self.launching_image, False, False, 0)
        child_box.pack_start(self.launching_title, False, False, 0)
        child_box.pack_start(self.launching_label, False, False, 0)
        child_box.pack_start(spinner, False, False, 0)

        parent_box.set_center_widget(child_box)

        self.stack.add_named(parent_box, "loading")

    def setup_game_view(self):
        """Initialize the game view where the game is embedded"""
        self.stack.add_named(self.socket, "game")

    # Callables
    def hide_actions(self):
        """Hide the in-game action buttons"""
        for key in list(self.action_buttons.keys()):
            self.action_buttons[key].hide()

    def show_actions(self):
        """Show the in-game action buttons"""
        for key in list(self.action_buttons.keys()):
            self.action_buttons[key].show()

    def set_subtitle(self, title):
        """Set the window subtitle"""
        self.hb.set_subtitle(title)

    def launch(self, title, icon_name, path):
        """Launch the specified application"""
        subtitle = _("Loading %s") % title

        if os.path.isfile(icon_name):
            self.launching_image.set_from_file(icon_name)
        else:
            self.launching_image.set_from_icon_name(icon_name,
                                                    Gtk.IconSize.DIALOG)
        self.launching_title.set_markup("<b>%s</b>" % title)
        self.set_view("loading", icon_name, subtitle)

        self.load_icon = icon_name
        self.load_title = title
        self.load_retry = 0
        self.loading_path = path
        self.threaded_launch()

    def threaded_launch(self):
        """
        Run the application launch in a separate thread, ensuring the window
        is correctly embedded
        """
        if self.loading:
            # Application is successfully launched, switch to the game view
            self.loading = False
            self.load_retry = 0

            # Stop the load thread
            GLib.source_remove(self.load_id)
            self.load_id = 0

            self.set_view("game", self.load_icon, self.load_title)
            self.grab_focus()
            return True
        if self.load_retry < 10:
            # Application is not fully launched yet
            self.loading = True
            self.launcher.launch(self.loading_path)
            self.load_id = GLib.timeout_add(1000, self.threaded_launch)
            self.grab_focus()
        else:
            # Application failed to load, return to the launcher
            self.loading = False
            self.load_retry = 0
            self.set_view("launcher")
            self.grab_focus()
            return True
        return False

    def set_view(self, name, icon_name=None, subtitle=None):
        """Change the view, setting the icon name and subtitle"""
        if name is "launcher":
            self.stack.set_transition_type(Gtk.StackTransitionType.OVER_RIGHT)
            self.hide_actions()
        if name is "loading":
            self.stack.set_transition_type(Gtk.StackTransitionType.OVER_LEFT)
            self.hide_actions()
        if name is "game":
            self.stack.set_transition_type(Gtk.StackTransitionType.OVER_LEFT)
            self.show_actions()

        title = self.title
        if icon_name is None:
            icon_name = self.appname
        if subtitle is None:
            subtitle = ""
        else:
            title = "%s - %s" % (title, subtitle)

        if os.path.isfile(icon_name):
            self.set_default_icon_from_file(icon_name)
        else:
            self.set_default_icon_name(icon_name)

        self.set_subtitle(subtitle)
        self.stack.set_visible_child_name(name)

        self.get_window().set_title(title)

        if name is "game":
            self.socket.grab_focus()

    # Events
    def socket_connect(self, socket):
        """Embedded window connected"""
        self.socket = self.launcher.get_socket()
        return True

    def socket_disconnect(self, socket):
        """Embedded window disconnected"""
        if self.loading:
            self.loading = False
            self.load_retry += 1
            GLib.source_remove(self.load_id)
            self.load_id = GLib.timeout_add(1000, self.threaded_launch)
        else:
            self.set_view("launcher")
        return True

    def on_keyboard_button_click(self, button, keycode, keyval):
        """Send keypress to embedded window on button click"""
        self.socket.grab_focus()
        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.keyval = keyval
        event.hardware_keycode = keycode
        event.window = self.get_window()
        event.set_device(self.keyboard)
        event.put()

    def treeview_cell_text_func(self, col, renderer, model, treeiter, data):
        """Render the treeview row"""
        name, comment, icon_name, exe = model[treeiter][:]
        markup = "<b>%s</b>\n%s" % (name, comment)
        renderer.set_property('markup', markup)
        return

    def treeview_cell_pixbuf_func(self, col, renderer, model, treeiter, data):
        """Render the treeview row"""
        name, comment, icon_name, exe = model[treeiter][:]
        if os.path.isfile(icon_name):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_name, 48, 48)
            renderer.set_property("pixbuf", pixbuf)
        return

    def on_activated(self, widget, treeiter, col):
        """Launch the selected application"""
        model = widget.get_model()
        name, comment, icon_name, exe = model[treeiter][:]
        self.launch(name, icon_name, exe)


class MyAboutDialog(Gtk.AboutDialog):
    def __init__(self, appname, title, parent):
        Gtk.AboutDialog.__init__(self)
        self.set_program_name(title)
        self.set_transient_for(parent)
        self.set_logo_icon_name(appname)
        self.set_modal(True)

        self.set_authors([
            "Sean Davis (SGT Puzzles)",
            "Simon Tatham (Simon Tatham's Portable Puzzle Collection)"
        ])
        self.set_copyright(
            "SGT Puzzles\n"
            "© 2016 Sean Davis\n"
            "\n"
            "Simon Tatham's Portable Puzzle Collection\n"
            "© 2004-2012 Simon Tatham"
        )
        self.set_artists([
            "Pasi Lallinaho"
        ])
        self.set_website("https://launchpad.net/sgt-launcher")
        self.set_website_label("SGT Puzzle Launcher on Launchpad")
        self.set_license_type(Gtk.License.GPL_3_0)

        self.connect("response", self.on_response)

    def on_response(self, dialog, response):
        self.hide()
        self.destroy()


class MyApplication(Gtk.Application):
    APPNAME = "sgt-launcher"
    TITLE = _("SGT Puzzles Collection")
    SETTINGS_KEY = "org.xubuntu.sgt-launcher"
    GAMES = [
        'blackbox',
        'bridges',
        'cube',
        'dominosa',
        'fifteen',
        'filling',
        'flip',
        'galaxies',
        'guess',
        'inertia',
        'keen',
        'lightup',
        'loopy',
        'magnets',
        'map',
        'mines',
        'net',
        'netslide',
        'pattern',
        'pearl',
        'pegs',
        'range',
        'rect',
        'samegame',
        'signpost',
        'singles',
        'sixteen',
        'slant',
        'solo',
        'tents',
        'towers',
        'twiddle',
        'undead',
        'unequal',
        'unruly',
        'untangle'
    ]

    def __init__(self):
        Gtk.Application.__init__(self)

    def do_activate(self):
        launchers = self.get_launchers()
        self.win = MyWindow(self, self.APPNAME, self.settings, launchers)
        self.win.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.settings = Gio.Settings.new(self.SETTINGS_KEY)

        menu = Gio.Menu()
        menu.append(_("Preferences"), "app.show-preferences")
        menu.append(_("About"), "app.about")
        menu.append(_("Quit"), "app.quit")
        self.set_app_menu(menu)

        prefs_action = Gio.SimpleAction.new("show-preferences", None)
        prefs_action.connect("activate", self.prefs_cb)
        self.add_action(prefs_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.about_cb)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.quit_cb)
        self.add_action(quit_action)

    def prefs_cb(self, action, parameter):
        print("Not implemented")

    def about_cb(self, action, parameter):
        """Show the about dialog"""
        about = MyAboutDialog(self.APPNAME, self.TITLE, self.win)
        about.run()

    def quit_cb(self, action, parameter):
        """Exit application"""
        self.quit()

    def get_launchers(self):
        """Get localized launcher contents"""
        flags = GLib.KeyFileFlags.NONE
        launchers = []
        for game in self.GAMES:
            for prefix in ["sgt", "puzzle"]:
                launcher = "applications/%s-%s.desktop" % (prefix, game)
                keyfile = GLib.KeyFile.new()
                try:
                    if (keyfile.load_from_data_dirs(launcher, flags)):
                        data = [
                            keyfile.get_value("Desktop Entry", "Name"),
                            keyfile.get_value("Desktop Entry", "Comment"),
                            keyfile.get_value("Desktop Entry", "Icon"),
                            keyfile.get_value("Desktop Entry", "Exec"),
                        ]
                        launchers.append(data)
                    break
                except GLib.Error:
                    pass
        launchers.sort()
        return launchers
