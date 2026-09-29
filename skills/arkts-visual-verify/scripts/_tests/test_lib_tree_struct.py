import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import lib_tree_struct as ts


def _tree():
    return {"app": {"launcher_activity": "x.y.SplashActivity"},
            "pages": [{"id": "SplashActivity", "navigation_contract": {"relationship_kind": "activity_root"},
                       "navigation": {"inbound": [], "outbound": [{"to": "MainActivity"}]}},
                      {"id": "MainActivity", "navigation": {"inbound": [], "outbound": []}},
                      {"id": "GuideActivity", "navigation": {"inbound": [], "outbound": []}},
                      {"id": "SignInActivity", "navigation": {"inbound": [], "outbound": []}}],
            "fragments": [{"id": "QueueFragment", "parent_in_nav": "MainActivity", "navigation_contract": {"relationship_kind": "tab"},
                           "functional_checks": [{"name": "刷新队列"}], "components": [{"text": "Queue"}]},
                          {"id": "InboxFragment", "parent_in_nav": "MainActivity", "navigation_contract": {"relationship_kind": "tab"}},
                          {"id": "StepOneFragment", "parent_in_nav": "GuideActivity", "navigation_contract": {"relationship_kind": "wizard_step"}}],
            "dialogs": [{"id": "ConsentDialog", "parent_in_nav": "SplashActivity", "navigation_contract": {"relationship_kind": "lifecycle_modal"}},
                        {"id": "RemoveFeedDialog", "parent_in_nav": "QueueFragment", "navigation_contract": {"relationship_kind": "dialog_trigger"}}]}


def test_first_launch_chain_from_structure_not_names():
    t = _tree()
    chain = ts.first_launch_chain(t)
    assert {"SplashActivity", "StepOneFragment", "GuideActivity", "ConsentDialog"} <= chain
    assert "RemoveFeedDialog" not in chain and "QueueFragment" not in chain
    assert ts.is_chain_node(t, "OnboardScreen") and not ts.is_chain_node(t, "PayAgreementDialog")


def test_main_container_and_home_start():
    t = _tree()
    assert ts.main_container(t) == "MainActivity"
    assert ts.home_start(t, {"MainActivity", "GuideActivity"}) == "MainActivity"
    t2 = {"app": {"launcher_activity": "a.SplashActivity"}, "pages": [{"id": "SplashActivity", "navigation": {"outbound": [{"to": "DashboardActivity"}]}}, {"id": "DashboardActivity"}], "fragments": [], "dialogs": []}
    assert ts.main_container(t2) == "DashboardActivity"          # 无承载事实 → launcher 自动跳转目标
    assert ts.home_start({"pages": [{"id": "MainScreen"}, {"id": "Other"}], "fragments": [], "dialogs": []}) == "MainScreen"


def test_login_ids_and_verb_bag():
    t = _tree()
    assert ts.login_ids(t) == {"SignInActivity"}                  # 语义兜底，不写死 LoginActivity
    bag = ts.project_verb_bag(t)
    assert "刷新队列" in bag and "Queue" in bag
