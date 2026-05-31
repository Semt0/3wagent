from app.core.schemas import UserQuery
from app.router.issue_router import route_issue


def test_routes_tax_question() -> None:
    issue = route_issue(UserQuery(question="香港公司向新加坡公司支付服务费是否有 withholding tax？"))

    assert issue.primary_domain == "tax"
    assert "HK" in issue.jurisdictions
    assert "SG" in issue.jurisdictions


def test_routes_funds_question() -> None:
    issue = route_issue(UserQuery(question="香港公司收到美国投资款，银行要求解释资金来源怎么办？"))

    assert issue.primary_domain == "funds"
    assert "HK" in issue.jurisdictions
    assert "US" in issue.jurisdictions


def test_tax_beats_funds_on_explicit_tax_question() -> None:
    issue = route_issue(UserQuery(question="香港公司向新加坡公司支付服务费，需要关注哪些税务和银行合规问题？"))

    assert issue.primary_domain == "tax"
    assert "funds" in issue.secondary_domains


def test_latin_keyword_does_not_match_inside_word() -> None:
    # "business" contains "us" and must NOT be read as the US jurisdiction;
    # the only jurisdiction signal here is "Singapore".
    issue = route_issue(UserQuery(question="Singapore business registration questions"))

    assert "US" not in issue.jurisdictions
    assert "SG" in issue.jurisdictions


def test_vat_does_not_match_inside_private() -> None:
    # "private" contains "vat" but this is a commercial (share transfer) question,
    # so the tax track must not be triggered by a false substring hit.
    issue = route_issue(UserQuery(question="private company 股权转让 需要什么文件"))

    assert issue.primary_domain == "commercial"
    assert "tax" not in issue.secondary_domains


def test_detects_payment_and_transaction_nature() -> None:
    issue = route_issue(UserQuery(question="香港公司向新加坡公司支付服务费是否需要扣缴税？"))

    assert issue.payment_type is not None and "服务费" in issue.payment_type
