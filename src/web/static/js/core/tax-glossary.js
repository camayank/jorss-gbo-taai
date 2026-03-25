/**
 * Tax Term Glossary — adds hover tooltips to elements with data-tax-term attribute.
 * Usage: <span data-tax-term="AGI">AGI</span>
 */
const TAX_GLOSSARY = {
    'AGI': 'Adjusted Gross Income \u2014 your total income minus specific deductions like IRA contributions and student loan interest.',
    'AMT': 'Alternative Minimum Tax \u2014 a parallel tax system that limits certain deductions to ensure minimum tax payment.',
    'MAGI': 'Modified Adjusted Gross Income \u2014 AGI with certain deductions added back, used for credit/deduction eligibility.',
    'EITC': 'Earned Income Tax Credit \u2014 a refundable credit for low-to-moderate income working individuals.',
    'QBI': 'Qualified Business Income \u2014 income from pass-through businesses eligible for a 20% deduction under Section 199A.',
    'SALT': 'State and Local Tax \u2014 deduction for state/local income, sales, and property taxes, capped at $10,000.',
    'HOH': 'Head of Household \u2014 filing status for unmarried taxpayers maintaining a home for a qualifying person.',
    'LTCG': 'Long-Term Capital Gains \u2014 profit from selling assets held over one year, taxed at preferential rates (0%, 15%, or 20%).',
    'SE Tax': 'Self-Employment Tax \u2014 Social Security and Medicare taxes for self-employed individuals (15.3%).',
    'NIIT': 'Net Investment Income Tax \u2014 3.8% surtax on investment income above certain thresholds.',
    'CTC': 'Child Tax Credit \u2014 up to $2,000 per qualifying child under 17.',
    'ACTC': 'Additional Child Tax Credit \u2014 refundable portion of CTC based on earned income over $2,500.',
    'IRC': 'Internal Revenue Code \u2014 the body of federal statutory tax law.',
    'W-2': 'Wage and Tax Statement \u2014 form from employers showing wages earned and taxes withheld.',
    '1099': 'Information return reporting various types of non-wage income (interest, dividends, freelance, etc.).',
    'Schedule C': 'Profit or Loss from Business \u2014 reports self-employment income and expenses.',
    'Schedule D': 'Capital Gains and Losses \u2014 reports gains/losses from selling investments.',
    'Schedule A': 'Itemized Deductions \u2014 for taxpayers who itemize instead of taking the standard deduction.',
    'NOL': 'Net Operating Loss \u2014 when deductions exceed income; can be carried forward to offset future taxable income.',
    'SEP-IRA': 'Simplified Employee Pension IRA \u2014 retirement plan for self-employed, up to 25% of compensation (max $70,000 for 2025).',
};

document.addEventListener('DOMContentLoaded', function() {
    var elements = document.querySelectorAll('[data-tax-term]');
    for (var i = 0; i < elements.length; i++) {
        var el = elements[i];
        var term = el.getAttribute('data-tax-term');
        var def = TAX_GLOSSARY[term];
        if (def) {
            el.setAttribute('title', def);
            el.style.borderBottom = '1px dotted var(--text-secondary, #6b7280)';
            el.style.cursor = 'help';
        }
    }
});
