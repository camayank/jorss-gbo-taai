"""Virtual Currency Tax Rules.

Comprehensive rules for cryptocurrency and digital asset taxation.
Based on IRS Notice 2014-21, Rev. Rul. 2019-24, Rev. Rul. 2023-14.
Tax Year: 2025

Rules VC001-VC075 covering:
- Core taxable events
- Cost basis methods
- Special transactions (NFTs, DeFi, staking)
- Foreign reporting requirements
- Specific identification and record keeping
"""

from __future__ import annotations

from .tax_rule_definitions import TaxRule, RuleCategory, RuleSeverity


# =============================================================================
# VIRTUAL CURRENCY RULES (75 rules)
# =============================================================================

VIRTUAL_CURRENCY_RULES = [
    # =========================================================================
    # Core Taxable Events (VC001-VC020)
    # =========================================================================
    TaxRule(
        rule_id="VC001",
        name="Virtual Currency Property Classification",
        description="Virtual currency is treated as property for federal tax purposes. General tax principles applicable to property transactions apply to transactions using virtual currency.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRS Notice 2014-21 Q&A-1",
        recommendation="Report all virtual currency transactions on Form 8949 and Schedule D as property sales"
    ),
    TaxRule(
        rule_id="VC002",
        name="Disposal as Taxable Event",
        description="Sale, exchange, or other disposition of virtual currency results in recognition of capital gain or loss. This includes selling crypto for fiat currency.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRS Notice 2014-21 Q&A-3",
        recommendation="Track all sales and exchanges of virtual currency for tax reporting"
    ),
    TaxRule(
        rule_id="VC003",
        name="Exchange Between Cryptocurrencies Taxable",
        description="Exchange of one virtual currency for another is a taxable event. Unlike-kind exchanges of crypto are not eligible for Section 1031 deferral.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRS Notice 2014-21 Q&A-6",
        recommendation="Report crypto-to-crypto exchanges as dispositions with gain/loss recognition"
    ),
    TaxRule(
        rule_id="VC004",
        name="Gain/Loss Calculation Method",
        description="Gain or loss on virtual currency is calculated as Fair Market Value at disposition minus Adjusted Basis (cost plus fees).",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 1001",
        recommendation="Maintain accurate records of acquisition cost and fees for all crypto purchases"
    ),
    TaxRule(
        rule_id="VC005",
        name="Mining Income Recognition",
        description="Virtual currency received from mining is ordinary income at fair market value when received. Taxpayer has dominion and control upon successful mining.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-8",
        recommendation="Report mining income as ordinary income on Schedule 1 or Schedule C if business"
    ),
    TaxRule(
        rule_id="VC006",
        name="Staking Rewards as Ordinary Income",
        description="Staking rewards are taxable as ordinary income at fair market value when the taxpayer gains dominion and control over the rewards.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Rul. 2023-14",
        recommendation="Report staking rewards as ordinary income when received"
    ),
    TaxRule(
        rule_id="VC007",
        name="Airdrop Income Recognition",
        description="Airdropped tokens are ordinary income at fair market value when taxpayer has dominion and control. Value at time of receipt is the taxpayer's basis.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Rul. 2019-24 Q&A-4",
        recommendation="Report airdrop value as other income; basis equals FMV at receipt"
    ),
    TaxRule(
        rule_id="VC008",
        name="Hard Fork Income Recognition",
        description="New cryptocurrency received from a hard fork is taxable income at fair market value if taxpayer has dominion and control. No income if crypto never received.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Rul. 2019-24 Q&A-4",
        recommendation="Report hard fork income when you gain access to new forked coins"
    ),
    TaxRule(
        rule_id="VC009",
        name="Payment for Goods/Services",
        description="Using virtual currency to pay for goods or services is a taxable disposition. Gain/loss calculated as FMV at time of payment minus basis.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-3",
        recommendation="Track all purchases made with crypto as taxable dispositions"
    ),
    TaxRule(
        rule_id="VC010",
        name="Receiving Crypto as Payment",
        description="Virtual currency received as payment for goods or services is ordinary income at fair market value. This applies to employees and contractors.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-9",
        recommendation="Report crypto received as compensation as W-2 wages or 1099 income"
    ),
    TaxRule(
        rule_id="VC011",
        name="Short-Term vs Long-Term Holding Period",
        description="Virtual currency held more than one year qualifies for long-term capital gains rates (0%, 15%, 20%). Held one year or less is short-term (ordinary rates).",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1222",
        recommendation="Consider holding crypto more than 1 year for preferential tax rates"
    ),
    TaxRule(
        rule_id="VC012",
        name="Form 8949 Reporting Requirement",
        description="All virtual currency sales, exchanges, and dispositions must be reported on Form 8949 with detailed transaction information.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Form 8949 Instructions",
        recommendation="Report each crypto transaction on Form 8949 with date acquired, date sold, proceeds, and cost basis"
    ),
    TaxRule(
        rule_id="VC013",
        name="Schedule D Reporting",
        description="Totals from Form 8949 flow to Schedule D for capital gains tax calculation. Short-term and long-term gains reported separately.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Schedule D Instructions",
        recommendation="Complete Schedule D to calculate total capital gain or loss from crypto"
    ),
    TaxRule(
        rule_id="VC014",
        name="Form 1040 Digital Asset Question",
        description="Form 1040 requires disclosure of any digital asset transactions during the tax year. Must answer Yes if you sold, exchanged, or received crypto.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="Form 1040 Line 1a",
        recommendation="Answer the digital asset question accurately on Form 1040"
    ),
    TaxRule(
        rule_id="VC015",
        name="Gifting Virtual Currency",
        description="Gifting crypto is not a taxable event for the giver, but recipient takes carryover basis. Gift tax may apply if over annual exclusion ($18,000 for 2025).",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1015",
        threshold=18000.0,
        recommendation="Document gifts of crypto; recipient inherits your cost basis"
    ),
    TaxRule(
        rule_id="VC016",
        name="Inherited Virtual Currency Basis",
        description="Inherited cryptocurrency receives stepped-up basis to fair market value at date of death. No capital gains tax on appreciation during decedent's lifetime.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1014",
        recommendation="Document FMV at death for inherited crypto assets"
    ),
    TaxRule(
        rule_id="VC017",
        name="Charitable Donation of Crypto",
        description="Donating appreciated crypto held over 1 year to qualified charity allows deduction of FMV without recognizing gain. Limited to 30% of AGI.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 170(b)(1)(C)",
        rate=0.30,
        recommendation="Consider donating highly appreciated crypto to charity to avoid capital gains"
    ),
    TaxRule(
        rule_id="VC018",
        name="Virtual Currency in IRA",
        description="Virtual currency can be held in self-directed IRAs. Transactions within IRA are tax-deferred (traditional) or tax-free (Roth). Special custodian required.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 408",
        recommendation="Consider holding crypto in self-directed IRA for tax advantages"
    ),
    TaxRule(
        rule_id="VC019",
        name="Lost or Stolen Cryptocurrency",
        description="Theft losses from crypto are generally not deductible under current law unless from federally declared disaster. Worthless crypto may qualify for capital loss.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 165(c)",
        recommendation="Document lost/stolen crypto thoroughly for potential future deduction"
    ),
    TaxRule(
        rule_id="VC020",
        name="Worthless Virtual Currency",
        description="Virtual currency that becomes completely worthless may be treated as capital loss. Must establish complete worthlessness in tax year claimed.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 165(g)",
        recommendation="Claim worthless crypto as capital loss in year it becomes completely worthless"
    ),

    # =========================================================================
    # Cost Basis Methods (VC021-VC035)
    # =========================================================================
    TaxRule(
        rule_id="VC021",
        name="FIFO Default Method",
        description="First-In-First-Out is the default cost basis method if taxpayer doesn't specifically identify lots sold. Oldest purchases considered sold first.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1",
        recommendation="Use FIFO as default unless specifically identifying lots"
    ),
    TaxRule(
        rule_id="VC022",
        name="LIFO Method",
        description="Last-In-First-Out method sells newest purchases first. May result in more short-term gains. Must be consistently applied.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.1012-1",
        recommendation="Consider LIFO in rising markets to reduce gain, but use consistently"
    ),
    TaxRule(
        rule_id="VC023",
        name="HIFO Method",
        description="Highest-In-First-Out method sells highest cost basis lots first, minimizing current tax. Acceptable under specific identification rules.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.1012-1(c)",
        recommendation="Consider HIFO to minimize taxable gains using specific identification"
    ),
    TaxRule(
        rule_id="VC024",
        name="Specific Identification Method",
        description="Taxpayer may specifically identify which lots are being sold to optimize tax outcome. Must adequately identify lots before or at time of sale.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1(c)",
        recommendation="Identify specific lots before sale for tax optimization"
    ),
    TaxRule(
        rule_id="VC025",
        name="Average Cost Not Generally Allowed",
        description="Average cost basis method is not allowed for virtual currency (unlike mutual funds). Must use FIFO or specific identification.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21",
        recommendation="Do not use average cost for crypto; use FIFO or specific identification"
    ),
    TaxRule(
        rule_id="VC026",
        name="Consistent Method Requirement",
        description="Once a cost basis method is chosen, it should be applied consistently. Changing methods may trigger IRS scrutiny.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1",
        recommendation="Apply chosen cost basis method consistently across transactions"
    ),
    TaxRule(
        rule_id="VC027",
        name="Transaction Fee Basis Adjustment",
        description="Transaction fees (gas fees, exchange fees) paid when acquiring crypto are added to cost basis. Fees on sale reduce net proceeds.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1012",
        recommendation="Include all fees in cost basis calculations"
    ),
    TaxRule(
        rule_id="VC028",
        name="Multi-Wallet Tracking",
        description="Cost basis must be tracked across all wallets and exchanges. Moving crypto between wallets is not a taxable event but basis must follow.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1",
        recommendation="Maintain unified tracking across all crypto wallets and exchanges"
    ),
    TaxRule(
        rule_id="VC029",
        name="Zero Cost Basis Warning",
        description="If cost basis cannot be established, IRS may treat basis as zero, resulting in maximum taxable gain. Maintain records to avoid.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1012",
        recommendation="Never lose cost basis records; reconstruct if necessary"
    ),
    TaxRule(
        rule_id="VC030",
        name="Foreign Exchange Basis",
        description="Crypto purchased on foreign exchanges must convert foreign currency cost to USD at acquisition date exchange rate.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 988",
        recommendation="Convert foreign currency costs to USD using acquisition date rate"
    ),
    TaxRule(
        rule_id="VC031",
        name="Lot Selection Documentation",
        description="When using specific identification, must document lot selection contemporaneously with trade. Retroactive lot selection is not permitted.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1(c)(2)",
        recommendation="Document specific lot identification at time of sale"
    ),
    TaxRule(
        rule_id="VC032",
        name="Adequate Identification Requirements",
        description="Specific identification requires specifying date acquired, amount, and unique identifier for the lot being sold.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Reg. 1.1012-1(c)(3)",
        recommendation="Include date, amount, and lot ID when identifying specific lots"
    ),
    TaxRule(
        rule_id="VC033",
        name="Universal Application Rule",
        description="Cost basis method must be applied universally across same type of virtual currency. Cannot use FIFO for some trades and LIFO for others.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Reg. 1.1012-1",
        recommendation="Apply same basis method to all transactions of same cryptocurrency"
    ),
    TaxRule(
        rule_id="VC034",
        name="Holding Period Determination",
        description="Holding period begins day after acquisition and ends on date of disposition. Includes weekends and holidays.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1223",
        recommendation="Track exact acquisition dates for accurate holding period calculation"
    ),
    TaxRule(
        rule_id="VC035",
        name="Tainted Holding Period",
        description="Holding period for received crypto from staking/mining begins when income is recognized, not when original stake was made.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1223",
        recommendation="Track holding period from income recognition date for rewards"
    ),

    # =========================================================================
    # Special Transactions (VC036-VC055)
    # =========================================================================
    TaxRule(
        rule_id="VC036",
        name="Wash Sale Consideration",
        description="Wash sale rules may apply to virtual currency under recent tax guidance. Repurchasing same crypto within 30 days of loss sale may disallow loss.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1091",
        recommendation="Avoid repurchasing same crypto within 30 days of selling at a loss"
    ),
    TaxRule(
        rule_id="VC037",
        name="NFT as Collectible Rate",
        description="Non-fungible tokens (NFTs) may be classified as collectibles subject to 28% maximum capital gains rate. Artwork and similar NFTs likely collectibles.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 1(h)(5)",
        rate=0.28,
        recommendation="Be aware that NFT gains may be taxed at 28% collectibles rate"
    ),
    TaxRule(
        rule_id="VC038",
        name="DeFi Yield Farming Income",
        description="Yield farming rewards are ordinary income at fair market value when received. Additional gains/losses on disposition are capital.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21",
        recommendation="Report DeFi yield as ordinary income when received"
    ),
    TaxRule(
        rule_id="VC039",
        name="Liquidity Pool Taxation",
        description="Adding to liquidity pools may be taxable if receiving LP tokens in exchange. Impermanent loss has uncertain tax treatment.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21",
        recommendation="Track LP deposits as potential taxable exchanges"
    ),
    TaxRule(
        rule_id="VC040",
        name="Wrapped Token Taxation",
        description="Wrapping/unwrapping tokens (e.g., ETH to WETH) may be taxable events if considered exchanges. Conservative treatment is taxable.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21 Q&A-6",
        recommendation="Consider wrapping transactions as potentially taxable exchanges"
    ),
    TaxRule(
        rule_id="VC041",
        name="Token Swap Taxation",
        description="Swapping tokens via DEX or swap protocol is taxable exchange. Gain/loss calculated on each swap.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-6",
        recommendation="Report all DEX swaps as taxable transactions"
    ),
    TaxRule(
        rule_id="VC042",
        name="Lending/Borrowing Crypto",
        description="Lending crypto may generate interest income taxable when received. Borrowing against crypto is generally not taxable.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 61(a)(4)",
        recommendation="Report crypto lending interest as ordinary income"
    ),
    TaxRule(
        rule_id="VC043",
        name="Margin Trading Gains/Losses",
        description="Margin trading gains are taxable; interest on margin loans may be deductible as investment interest expense.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 163(d)",
        recommendation="Deduct margin interest as investment interest if itemizing"
    ),
    TaxRule(
        rule_id="VC044",
        name="Futures and Options on Crypto",
        description="Crypto futures and options may be Section 1256 contracts with 60/40 capital gains treatment. Exchange-traded only.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 1256",
        recommendation="Report regulated crypto futures on Form 6781 for 60/40 treatment"
    ),
    TaxRule(
        rule_id="VC045",
        name="Stablecoin Transactions",
        description="Stablecoin transactions are taxable even though value typically stable. Small gains/losses may still occur.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21",
        recommendation="Track stablecoin transactions for minimal but reportable gains/losses"
    ),
    TaxRule(
        rule_id="VC046",
        name="Cross-Chain Bridge Transactions",
        description="Moving crypto across blockchains via bridges may trigger taxable events if different tokens received.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21 Q&A-6",
        recommendation="Evaluate bridge transactions for potential taxable exchanges"
    ),
    TaxRule(
        rule_id="VC047",
        name="Rebasing Token Taxation",
        description="Rebasing tokens that increase supply to wallets may generate taxable income on each rebase event.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="Rev. Rul. 2023-14",
        recommendation="Report rebasing token increases as ordinary income"
    ),
    TaxRule(
        rule_id="VC048",
        name="Play-to-Earn Gaming Rewards",
        description="Tokens earned through blockchain gaming are ordinary income at fair market value when received.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21",
        recommendation="Report gaming rewards as ordinary income"
    ),
    TaxRule(
        rule_id="VC049",
        name="FBAR Foreign Exchange Reporting",
        description="Foreign crypto exchange accounts may require FBAR filing if aggregate foreign accounts exceed $10,000 at any time.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="31 USC 5314",
        threshold=10000.0,
        recommendation="File FBAR for foreign crypto exchange accounts over $10,000"
    ),
    TaxRule(
        rule_id="VC050",
        name="Form 8938 Foreign Crypto Reporting",
        description="Foreign crypto accounts may require Form 8938 reporting if exceeding FATCA thresholds ($50,000 single/$100,000 MFJ at year end).",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6038D",
        thresholds_by_status={
            "single": 50000.0,
            "married_joint": 100000.0,
            "married_separate": 50000.0,
            "head_of_household": 50000.0
        },
        recommendation="File Form 8938 if foreign crypto exceeds FATCA thresholds"
    ),
    TaxRule(
        rule_id="VC051",
        name="Proof of Stake Validator Income",
        description="Block rewards received by validators in proof-of-stake networks are ordinary income at fair market value when received.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Rev. Rul. 2023-14",
        recommendation="Report validator rewards as ordinary income"
    ),
    TaxRule(
        rule_id="VC052",
        name="DAO Token Distribution",
        description="Tokens distributed by DAOs for participation or governance may be ordinary income at fair market value.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRS Notice 2014-21",
        recommendation="Report DAO token distributions as potential ordinary income"
    ),
    TaxRule(
        rule_id="VC053",
        name="Token Burns and Buybacks",
        description="Tokens received from buyback programs may be taxable. Participating in token burns does not generate deductible loss.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 165",
        recommendation="Voluntary token burns are not deductible losses"
    ),
    TaxRule(
        rule_id="VC054",
        name="Referral and Bonus Rewards",
        description="Crypto received as referral bonuses or promotional rewards is ordinary income at fair market value.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 61",
        recommendation="Report crypto referral bonuses as other income"
    ),
    TaxRule(
        rule_id="VC055",
        name="ICO/IDO Participation",
        description="Exchanging crypto for new tokens in ICO/IDO is a taxable event. Basis in new tokens equals FMV at acquisition.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-6",
        recommendation="Report ICO/IDO participation as taxable exchanges"
    ),

    # =========================================================================
    # Self-Employment and Business (VC056-VC065)
    # =========================================================================
    TaxRule(
        rule_id="VC056",
        name="Mining as Business Activity",
        description="Mining conducted with continuity, regularity, and profit intent is a trade or business subject to self-employment tax.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-9",
        recommendation="Report mining business on Schedule C with SE tax"
    ),
    TaxRule(
        rule_id="VC057",
        name="Mining Equipment Depreciation",
        description="Mining equipment used in business may be depreciated. Section 179 or MACRS depreciation available.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 167",
        recommendation="Depreciate mining equipment over useful life or use Section 179"
    ),
    TaxRule(
        rule_id="VC058",
        name="Mining Electricity Deduction",
        description="Electricity costs for mining business are deductible business expenses. Home office portion if mining at home.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 162",
        recommendation="Deduct electricity costs allocable to mining operations"
    ),
    TaxRule(
        rule_id="VC059",
        name="Staking as Business vs Hobby",
        description="Staking income may be business income if conducted with regularity and profit motive, otherwise hobby income.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 183",
        recommendation="Evaluate staking activity for trade or business status"
    ),
    TaxRule(
        rule_id="VC060",
        name="Crypto Trading Business",
        description="Active crypto traders may qualify as traders in securities with mark-to-market election (Section 475). Requires substantial activity.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.MEDIUM,
        irs_reference="IRC Section 475",
        recommendation="Consider trader status for frequent crypto trading; requires 475(f) election"
    ),
    TaxRule(
        rule_id="VC061",
        name="Business Expense for Crypto Software",
        description="Software and subscription costs for crypto tracking, trading, and tax reporting are deductible business expenses.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 162",
        recommendation="Deduct crypto software costs as business expenses"
    ),
    TaxRule(
        rule_id="VC062",
        name="Hardware Wallet Deduction",
        description="Hardware wallets used for business crypto may be deductible. Personal use allocation required if mixed use.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.LOW,
        irs_reference="IRC Section 162",
        recommendation="Deduct hardware wallet costs for business use"
    ),
    TaxRule(
        rule_id="VC063",
        name="Crypto Payment Processing",
        description="Businesses accepting crypto as payment recognize income at FMV when received. Must track for gain/loss on subsequent sale.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRS Notice 2014-21 Q&A-7",
        recommendation="Record business crypto receipts at FMV; track for later disposal"
    ),
    TaxRule(
        rule_id="VC064",
        name="Employee Crypto Compensation",
        description="Crypto paid to employees is wages subject to withholding. Employer must report FMV on W-2 and withhold employment taxes.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRS Notice 2014-21 Q&A-11",
        recommendation="Withhold payroll taxes on crypto compensation to employees"
    ),
    TaxRule(
        rule_id="VC065",
        name="Contractor Crypto Payments",
        description="Crypto paid to contractors is 1099 reportable income at FMV. Form 1099-NEC required if $600 or more.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6041",
        threshold=600.0,
        recommendation="Issue 1099-NEC for crypto payments to contractors over $600"
    ),

    # =========================================================================
    # Reporting and Record Keeping (VC066-VC075)
    # =========================================================================
    TaxRule(
        rule_id="VC066",
        name="Transaction Record Requirements",
        description="Must maintain records of date, FMV at time of transaction, and basis for all crypto transactions.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6001",
        recommendation="Keep detailed records of all crypto transactions indefinitely"
    ),
    TaxRule(
        rule_id="VC067",
        name="Third-Party Reporting Form 1099",
        description="Exchanges may issue Form 1099-B, 1099-MISC, or 1099-K for crypto transactions. Cross-reference with your records.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6045",
        recommendation="Reconcile exchange 1099s with your transaction records"
    ),
    TaxRule(
        rule_id="VC068",
        name="Broker Reporting Requirements",
        description="Starting 2025, crypto brokers must report gross proceeds and cost basis on Form 1099-DA under new regulations.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="Infrastructure Investment and Jobs Act",
        recommendation="Expect Form 1099-DA from exchanges starting 2025"
    ),
    TaxRule(
        rule_id="VC069",
        name="Statute of Limitations",
        description="IRS generally has 3 years to audit; 6 years if 25%+ of income omitted. Fraud has no limitation.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6501",
        recommendation="Keep crypto records for at least 6 years after filing"
    ),
    TaxRule(
        rule_id="VC070",
        name="Amended Return for Crypto",
        description="Unreported crypto income may require filing amended returns (Form 1040-X) for prior years.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 6013(b)",
        recommendation="File amended returns to correct crypto reporting errors"
    ),
    TaxRule(
        rule_id="VC071",
        name="Voluntary Disclosure Program",
        description="Unreported crypto may qualify for IRS voluntary disclosure program to avoid criminal penalties.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRM 9.5.11.9",
        recommendation="Consider voluntary disclosure for significant unreported crypto"
    ),
    TaxRule(
        rule_id="VC072",
        name="Penalty for Failure to Report",
        description="Failure to report crypto income may result in accuracy-related penalty (20%) or fraud penalty (75%).",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 6662/6663",
        rate=0.20,
        recommendation="Accurately report all crypto to avoid substantial penalties"
    ),
    TaxRule(
        rule_id="VC073",
        name="Criminal Tax Evasion Risk",
        description="Willful failure to report crypto income may constitute tax evasion with criminal penalties including imprisonment.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 7201",
        recommendation="Never willfully fail to report crypto income"
    ),
    TaxRule(
        rule_id="VC074",
        name="John Doe Summons",
        description="IRS has used John Doe summonses to obtain records from crypto exchanges. Your records may be obtained.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.HIGH,
        irs_reference="IRC Section 7609(f)",
        recommendation="Assume IRS has or will obtain your exchange records"
    ),
    TaxRule(
        rule_id="VC075",
        name="International Crypto Reporting",
        description="US persons must report worldwide crypto income. Foreign exchanges and wallets included in reporting requirements.",
        category=RuleCategory.VIRTUAL_CURRENCY,
        severity=RuleSeverity.CRITICAL,
        irs_reference="IRC Section 61",
        recommendation="Report all worldwide crypto income to IRS"
    ),
]
