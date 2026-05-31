FUNDS_KEYWORDS = [
    "汇款",
    "汇出",
    "汇入",
    "跨境付款",
    "银行",
    "kyc",
    "aml",
    "ofac",
    "制裁",
    "资金来源",
    "账户",
    "外汇",
    "remittance",
    "sanctions",
]

TAX_KEYWORDS = [
    "税",
    "扣缴",
    "withholding",
    "gst",
    "vat",
    "利得税",
    "irs",
    "iras",
    "ird",
    "税收协定",
    "资本利得",
    "royalty",
    "dividend",
    "interest",
]

COMMERCIAL_KEYWORDS = [
    "公司设立",
    "股权转让",
    "董事",
    "股东",
    "合同",
    "牌照",
    "商业登记",
    "许可",
    "投资准入",
    "director",
    "shareholder",
    "license",
]

JURISDICTION_KEYWORDS = {
    "US": ["美国", "us", "u.s.", "united states", "delaware", "irs", "ofac", "fincen"],
    "HK": ["香港", "hong kong", "hk", "ird", "hkma", "sfc"],
    "SG": ["新加坡", "singapore", "sg", "iras", "mas", "acra"],
}

# Payment / income characterization. Mainly feeds tax analysis and the
# "付款/交易性质" line of the report.
PAYMENT_TYPE_KEYWORDS = {
    "股息/分红": ["股息", "股利", "分红", "红利", "dividend", "dividends"],
    "利息": ["利息", "interest"],
    "特许权使用费": ["特许权使用费", "版税", "royalty", "royalties"],
    "服务费": ["服务费", "咨询费", "管理费", "service fee", "management fee", "consulting fee"],
    "资本利得": ["资本利得", "股权转让所得", "capital gain", "capital gains"],
    "工资薪金": ["工资", "薪金", "salary", "payroll"],
}

# High-level nature of the underlying transaction.
TRANSACTION_TYPE_KEYWORDS = {
    "跨境付款/汇款": ["跨境付款", "汇款", "汇出", "汇入", "remittance", "cross-border payment"],
    "股权转让": ["股权转让", "share transfer", "equity transfer"],
    "公司设立": ["公司设立", "注册公司", "incorporation", "company formation"],
    "投资入股": ["投资款", "投资入股", "增资", "investment"],
}

