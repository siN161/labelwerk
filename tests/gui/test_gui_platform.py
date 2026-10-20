def test_gui_tests_never_open_real_windows(qapp):
    # GUI tests always run offscreen – even if the session sets QT_QPA_PLATFORM=wayland
    assert qapp.platformName() == "offscreen"
