"""Sidebar navigation between the five pages."""

from src.widgets.sidebar import PAGE_ORDER, Sidebar


def test_sidebar_has_five_buttons():
    sidebar = Sidebar()
    assert len(sidebar.buttons()) == 5
    assert [b.page_id for b in sidebar.buttons()] == PAGE_ORDER


def test_default_page_is_home(qapp, config, app_state, theme_service):
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    assert window.current_page_id() == "home"
    window.close()


def test_navigate_to_every_page(qapp, config, app_state, theme_service):
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    for page_id in PAGE_ORDER:
        window.navigate(page_id)
        assert window.current_page_id() == page_id
        assert window.stack.currentWidget() is window.pages[page_id]
    window.close()


def test_sidebar_click_drives_navigation(qapp, config, app_state, theme_service):
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    window.sidebar._buttons["settings"].click()
    assert window.current_page_id() == "settings"
    window.sidebar._buttons["about"].click()
    assert window.current_page_id() == "about"
    window.close()


def test_home_view_all_navigates_to_queue(qapp, config, app_state, theme_service):
    from src.main_window import MainWindow

    window = MainWindow(config, app_state, theme_service)
    # The "View All" link on Home emits navigate_requested("queue").
    window.pages["home"].navigate_requested.emit("queue")
    assert window.current_page_id() == "queue"
    window.close()
