"""extract_dialog_ids：关闭/确认键只在可点按钮类控件里分类（2026-09-10，AntennaPod 试跑实爆）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract_dialog_ids as ed  # noqa: E402


def test_non_action_widgets_are_not_close_or_confirm(tmp_path):
    lay = tmp_path / "dialog_x.xml"
    lay.write_text('''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">
  <CheckBox android:id="@+id/skipSilence" android:text="Skip silence"/>
  <EditText android:id="@+id/etxtSkipIntro"/>
  <TextView android:id="@+id/labelSkipIntro"/>
  <com.google.android.material.button.MaterialButton android:id="@+id/cancelButton"/>
  <Button android:id="@+id/removeConfirmButton"/>
  <TextView android:id="@+id/tv_sure"/>
</LinearLayout>''', encoding="utf-8")
    ids = ed.extract_actionable_ids(lay)
    assert ids == ["cancelButton", "removeConfirmButton", "tv_sure"]
    close, confirm = ed.classify(ids)
    assert close == ["cancelButton"] and confirm == ["removeConfirmButton"]
    assert set(ed.extract_ids(lay)) >= {"skipSilence", "etxtSkipIntro", "labelSkipIntro"}   # all_ids 仍全量
