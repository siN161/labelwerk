def test_gui_tests_never_open_real_windows(qapp):
    # GUI-Tests laufen immer offscreen – auch wenn die Sitzung QT_QPA_PLATFORM=wayland setzt
    assert qapp.platformName() == "offscreen"
