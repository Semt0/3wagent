from app.graph.policy_graph import run_policy_workflow


def test_report_matches_readme_shape() -> None:
    report = run_policy_workflow(
        question="香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？"
    )

    # Sections required by the README "Example Output Shape".
    for section in (
        "【问题识别】",
        "付款/交易性质：",
        "【简要结论】",
        "【法规与政策索引】",
        "适用点：",
        "【结论可靠性】",
    ):
        assert section in report, f"missing section: {section}"

    # Internal routing debug info must not leak into the user-facing report.
    assert "路由原因" not in report
    assert "Routing scores" not in report


def test_summary_lists_each_relevant_domain() -> None:
    # Tax (primary) + funds (secondary) -> at least two numbered conclusions.
    report = run_policy_workflow(
        question="香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？"
    )
    summary = report.split("【简要结论】", 1)[1].split("【", 1)[0]

    assert "1." in summary
    assert "2." in summary
