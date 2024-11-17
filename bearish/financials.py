from datetime import datetime

import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
import yfinance as yf



if TYPE_CHECKING:
    from bearish.database.crud import BearishDb
    from bearish.models.base import Equity


class BaseFinancials(BaseModel):
    accounts_payable: Optional[float] = Field(None, alias="Accounts Payable", description="Amount owed to suppliers and creditors")
    accounts_receivable: Optional[float] = Field(None, alias="Accounts Receivable", description="Amount due from customers")
    accumulated_depreciation: Optional[float] = Field(None, alias="Accumulated Depreciation", description="Total depreciation of assets over time")
    available_for_sale_securities: Optional[float] = Field(None, alias="Available For Sale Securities", description="Marketable securities available for sale")
    basic_average_shares: Optional[float] = Field(None, alias="Basic Average Shares", description="Average shares outstanding used in basic EPS calculation")
    basic_eps: Optional[float] = Field(None, alias="Basic EPS", description="Earnings per share for basic shares outstanding")
    beginning_cash_position: Optional[float] = Field(None, alias="Beginning Cash Position", description="Starting cash balance for the period")
    capital_expenditure: Optional[float] = Field(None, alias="Capital Expenditure", description="Spending on fixed assets")
    capital_lease_obligations: Optional[float] = Field(None, alias="Capital Lease Obligations", description="Obligations under capital leases")
    capital_stock: Optional[float] = Field(None, alias="Capital Stock", description="Value of capital stock issued by the company")
    cash_and_cash_equivalents: Optional[float] = Field(None, alias="Cash And Cash Equivalents", description="Cash on hand and other liquid assets")
    cash_cash_equivalents_and_short_term_investments: Optional[float] = Field(None, alias="Cash Cash Equivalents And Short Term Investments", description="Total of cash, equivalents, and short-term investments")
    cash_dividends_paid: Optional[float] = Field(None, alias="Cash Dividends Paid", description="Cash dividends paid to shareholders")
    cash_equivalents: Optional[float] = Field(None, alias="Cash Equivalents", description="Highly liquid short-term investments")
    cash_financial: Optional[float] = Field(None, alias="Cash Financial", description="Cash related to financial operations")
    cash_flow_from_continuing_financing_activities: Optional[float] = Field(None, alias="Cash Flow From Continuing Financing Activities", description="Cash flow from ongoing financing activities")
    cash_flow_from_continuing_investing_activities: Optional[float] = Field(None, alias="Cash Flow From Continuing Investing Activities", description="Cash flow from ongoing investing activities")
    cash_flow_from_continuing_operating_activities: Optional[float] = Field(None, alias="Cash Flow From Continuing Operating Activities", description="Cash flow from ongoing operating activities")
    change_in_account_payable: Optional[float] = Field(None, alias="Change In Account Payable", description="Change in accounts payable over the period")
    change_in_inventory: Optional[float] = Field(None, alias="Change In Inventory", description="Change in inventory balance over the period")
    change_in_other_current_assets: Optional[float] = Field(None, alias="Change In Other Current Assets", description="Change in other current assets")
    change_in_other_current_liabilities: Optional[float] = Field(None, alias="Change In Other Current Liabilities", description="Change in other current liabilities")
    change_in_other_working_capital: Optional[float] = Field(None, alias="Change In Other Working Capital", description="Change in other components of working capital")
    change_in_payable: Optional[float] = Field(None, alias="Change In Payable", description="Change in payable accounts")
    change_in_payables_and_accrued_expense: Optional[float] = Field(None, alias="Change In Payables And Accrued Expense", description="Change in payables and accrued expenses")
    change_in_receivables: Optional[float] = Field(None, alias="Change In Receivables", description="Change in receivables balance")
    change_in_working_capital: Optional[float] = Field(None, alias="Change In Working Capital", description="Overall change in working capital")
    changes_in_account_receivables: Optional[float] = Field(None, alias="Changes In Account Receivables", description="Changes in accounts receivable")
    changes_in_cash: Optional[float] = Field(None, alias="Changes In Cash", description="Changes in cash balance")
    commercial_paper: Optional[float] = Field(None, alias="Commercial Paper", description="Short-term unsecured promissory notes issued")
    common_stock: Optional[float] = Field(None, alias="Common Stock", description="Value of common stock issued")
    common_stock_dividend_paid: Optional[float] = Field(None, alias="Common Stock Dividend Paid", description="Dividend paid on common stock")
    common_stock_equity: Optional[float] = Field(None, alias="Common Stock Equity", description="Total equity attributable to common stock")
    common_stock_issuance: Optional[float] = Field(None, alias="Common Stock Issuance", description="Proceeds from issuing common stock")
    common_stock_payments: Optional[float] = Field(None, alias="Common Stock Payments", description="Payments related to common stock transactions")
    cost_of_revenue: Optional[float] = Field(None, alias="Cost Of Revenue", description="Total cost to produce goods or services")
    current_assets: Optional[float] = Field(None, alias="Current Assets", description="Total of all current assets")
    current_capital_lease_obligation: Optional[float] = Field(None, alias="Current Capital Lease Obligation", description="Current portion of capital lease obligations")
    current_debt: Optional[float] = Field(None, alias="Current Debt", description="Total debt due within the year")
    current_debt_and_capital_lease_obligation: Optional[float] = Field(None, alias="Current Debt And Capital Lease Obligation", description="Total of current debt and capital lease obligations")
    current_deferred_liabilities: Optional[float] = Field(None, alias="Current Deferred Liabilities", description="Deferred liabilities due within the year")
    current_deferred_revenue: Optional[float] = Field(None, alias="Current Deferred Revenue", description="Deferred revenue due within the year")
    current_liabilities: Optional[float] = Field(None, alias="Current Liabilities", description="Total of all current liabilities")
    deferred_income_tax: Optional[float] = Field(None, alias="Deferred Income Tax", description="Deferred income tax liability")
    deferred_tax: Optional[float] = Field(None, alias="Deferred Tax", description="Total deferred tax liability")
    depreciation_amortization_depletion: Optional[float] = Field(None, alias="Depreciation Amortization Depletion", description="Total depreciation, amortization, and depletion expense")
    depreciation_and_amortization: Optional[float] = Field(None, alias="Depreciation And Amortization", description="Total depreciation and amortization expense")
    diluted_average_shares: Optional[float] = Field(None, alias="Diluted Average Shares", description="Average diluted shares outstanding")
    diluted_eps: Optional[float] = Field(None, alias="Diluted EPS", description="Earnings per share for diluted shares")
    diluted_ni_availto_com_stockholders: Optional[float] = Field(None, alias="Diluted NI Availto Com Stockholders", description="Diluted net income available to common stockholders")
    ebit: Optional[float] = Field(None, alias="EBIT", description="Earnings before interest and taxes")
    ebitda: Optional[float] = Field(None, alias="EBITDA", description="Earnings before interest, taxes, depreciation, and amortization")
    end_cash_position: Optional[float] = Field(None, alias="End Cash Position", description="Ending cash balance for the period")
    financing_cash_flow: Optional[float] = Field(None, alias="Financing Cash Flow", description="Cash flow from financing activities")
    finished_goods: Optional[float] = Field(None, alias="Finished Goods", description="Inventory of finished goods")
    free_cash_flow: Optional[float] = Field(None, alias="Free Cash Flow", description="Cash available after capital expenditures")
    gains_losses_not_affecting_retained_earnings: Optional[float] = Field(None,
        alias="Gains Losses Not Affecting Retained Earnings",
        description="Gains and losses excluded from retained earnings")
    gross_ppe: Optional[float] = Field(None, alias="Gross PPE", description="Gross property, plant, and equipment")
    gross_profit: Optional[float] = Field(None, alias="Gross Profit",
                                          description="Revenue after deducting cost of goods sold")
    income_tax_paid_supplemental_data: Optional[float] = Field(None, alias="Income Tax Paid Supplemental Data",
                                                               description="Supplemental data on income taxes paid")
    income_tax_payable: Optional[float] = Field(None, alias="Income Tax Payable", description="Tax liability due")
    interest_expense: Optional[float] = Field(None, alias="Interest Expense", description="Interest expense for the period")
    interest_expense_non_operating: Optional[float] = Field(None, alias="Interest Expense Non Operating",
                                                            description="Non-operating interest expense")
    interest_income: Optional[float] = Field(None, alias="Interest Income", description="Income from interest earned")
    interest_income_non_operating: Optional[float] = Field(None, alias="Interest Income Non Operating",
                                                           description="Non-operating interest income")
    interest_paid_supplemental_data: Optional[float] = Field(None, alias="Interest Paid Supplemental Data",
                                                             description="Supplemental data on interest paid")
    inventory: Optional[float] = Field(None, alias="Inventory", description="Total inventory held")
    invested_capital: Optional[float] = Field(None, alias="Invested Capital", description="Total invested capital")
    investing_cash_flow: Optional[float] = Field(None, alias="Investing Cash Flow",
                                                 description="Cash flow from investing activities")
    investmentin_financial_assets: Optional[float] = Field(None, alias="Investmentin Financial Assets",
                                                           description="Investment in financial assets")
    investments_and_advances: Optional[float] = Field(None, alias="Investments And Advances",
                                                      description="Total investments and advances")
    issuance_of_capital_stock: Optional[float] = Field(None, alias="Issuance Of Capital Stock",
                                                       description="Capital stock issuance amount")
    issuance_of_debt: Optional[float] = Field(None, alias="Issuance Of Debt", description="Debt issuance amount")
    land_and_improvements: Optional[float] = Field(None, alias="Land And Improvements",
                                                   description="Value of land and improvements")
    leases: Optional[float] = Field(None, alias="Leases", description="Lease-related obligations")
    long_term_capital_lease_obligation: Optional[float] = Field(None, alias="Long Term Capital Lease Obligation",
                                                                description="Long-term capital lease obligations")
    long_term_debt: Optional[float] = Field(None, alias="Long Term Debt", description="Debt obligations due beyond one year")
    long_term_debt_and_capital_lease_obligation: Optional[float] = Field(None,
        alias="Long Term Debt And Capital Lease Obligation",
        description="Total of long-term debt and capital lease obligations")
    long_term_debt_issuance: Optional[float] = Field(None, alias="Long Term Debt Issuance",
                                                     description="Issuance of long-term debt")
    long_term_debt_payments: Optional[float] = Field(None, alias="Long Term Debt Payments",
                                                     description="Payments on long-term debt")
    machinery_furniture_equipment: Optional[float] = Field(None, alias="Machinery Furniture Equipment",
                                                           description="Value of machinery, furniture, and equipment")
    net_business_purchase_and_sale: Optional[float] = Field(None, alias="Net Business Purchase And Sale",
                                                            description="Net amount from business purchases and sales")
    net_common_stock_issuance: Optional[float] = Field(None, alias="Net Common Stock Issuance",
                                                       description="Net common stock issuance")
    net_debt: Optional[float] = Field(None, alias="Net Debt", description="Net amount of debt")
    net_income: Optional[float] = Field(None, alias="Net Income", description="Total net income")
    net_income_common_stockholders: Optional[float] = Field(None, alias="Net Income Common Stockholders",
                                                            description="Net income available to common stockholders")
    net_income_continuous_operations: Optional[float] = Field(None, alias="Net Income Continuous Operations",
                                                              description="Net income from continuous operations")
    net_income_from_continuing_and_discontinued_operation: Optional[float] = Field(None,
        alias="Net Income From Continuing And Discontinued Operation", description="Net income from all operations")
    net_income_from_continuing_operation_net_minority_interest: Optional[float] = Field(None,
        alias="Net Income From Continuing Operation Net Minority Interest",
        description="Net income from continuing operations excluding minority interest")
    net_income_from_continuing_operations: Optional[float] = Field(None, alias="Net Income From Continuing Operations",
                                                                   description="Net income from continuing operations")
    net_income_including_noncontrolling_interests: Optional[float] = Field(None,
        alias="Net Income Including Noncontrolling Interests",
        description="Net income including noncontrolling interests")
    net_interest_income: Optional[float] = Field(None, alias="Net Interest Income", description="Net interest income")
    net_investment_purchase_and_sale: Optional[float] = Field(None, alias="Net Investment Purchase And Sale",
                                                              description="Net result of investment purchases and sales")
    net_issuance_payments_of_debt: Optional[float] = Field(None, alias="Net Issuance Payments Of Debt",
                                                           description="Net issuance and payments of debt")
    net_long_term_debt_issuance: Optional[float] = Field(None, alias="Net Long Term Debt Issuance",
                                                         description="Net issuance of long-term debt")
    net_non_operating_interest_income_expense: Optional[float] = Field(None,
        alias="Net Non Operating Interest Income Expense", description="Net non-operating interest income or expense")
    net_other_financing_charges: Optional[float] = Field(None, alias="Net Other Financing Charges",
                                                         description="Other financing charges")
    net_other_investing_changes: Optional[float] = Field(None, alias="Net Other Investing Changes",
                                                         description="Other changes in investing activities")
    net_ppe: Optional[float] = Field(None, alias="Net PPE", description="Net value of property, plant, and equipment")
    net_ppe_purchase_and_sale: Optional[float] = Field(None, alias="Net PPE Purchase And Sale",
                                                       description="Net purchases and sales of PPE")
    net_short_term_debt_issuance: Optional[float] = Field(None, alias="Net Short Term Debt Issuance",
                                                          description="Net issuance of short-term debt")
    net_tangible_assets: Optional[float] = Field(None, alias="Net Tangible Assets", description="Net tangible assets")
    non_current_deferred_assets: Optional[float] = Field(None, alias="Non Current Deferred Assets",
                                                         description="Deferred assets not due within one year")
    non_current_deferred_taxes_assets: Optional[float] = Field(None, alias="Non Current Deferred Taxes Assets",
                                                               description="Deferred tax assets not due within one year")
    normalized_ebitda: Optional[float] = Field(None, alias="Normalized EBITDA",
                                               description="Normalized EBITDA for the period")
    normalized_income: Optional[float] = Field(None, alias="Normalized Income",
                                               description="Normalized income for the period")
    operating_cash_flow: Optional[float] = Field(None, alias="Operating Cash Flow",
                                                 description="Cash flow from operating activities")
    operating_expense: Optional[float] = Field(None, alias="Operating Expense", description="Total operating expenses")
    operating_income: Optional[float] = Field(None, alias="Operating Income", description="Income from operations")
    operating_revenue: Optional[float] = Field(None, alias="Operating Revenue", description="Total operating revenue")
    ordinary_shares_number: Optional[float] = Field(None, alias="Ordinary Shares Number",
                                                    description="Number of ordinary shares outstanding")
    other_current_assets: Optional[float] = Field(None, alias="Other Current Assets",
                                                  description="Other assets classified as current")
    other_current_borrowings: Optional[float] = Field(None, alias="Other Current Borrowings",
                                                      description="Other current borrowings")
    other_current_liabilities: Optional[float] = Field(None, alias="Other Current Liabilities",
                                                       description="Other current liabilities")
    other_equity_adjustments: Optional[float] = Field(None, alias="Other Equity Adjustments",
                                                      description="Other adjustments to equity")
    other_income_expense: Optional[float] = Field(None, alias="Other Income Expense",
                                                  description="Other income or expense not included in operating income")
    other_investments: Optional[float] = Field(None, alias="Other Investments", description="Other investment assets")
    other_non_cash_items: Optional[float] = Field(None, alias="Other Non Cash Items",
                                                  description="Non-cash items not classified elsewhere")
    other_non_current_assets: Optional[float] = Field(None, alias="Other Non Current Assets",
                                                      description="Other non-current assets")
    other_non_current_liabilities: Optional[float] = Field(None, alias="Other Non Current Liabilities",
                                                           description="Other non-current liabilities")
    other_non_operating_income_expenses: Optional[float] = Field(None, alias="Other Non Operating Income Expenses",
                                                                 description="Other non-operating income or expenses")
    other_properties: Optional[float] = Field(None, alias="Other Properties", description="Other properties held")
    other_receivables: Optional[float] = Field(None, alias="Other Receivables", description="Other receivables")
    other_short_term_investments: Optional[float] = Field(None, alias="Other Short Term Investments",
                                                          description="Other short-term investments")
    payables: Optional[float] = Field(None, alias="Payables", description="Total payables")
    payables_and_accrued_expenses: Optional[float] = Field(None, alias="Payables And Accrued Expenses",
                                                           description="Total payables and accrued expenses")
    pretax_income: Optional[float] = Field(None, alias="Pretax Income", description="Income before tax")
    properties: Optional[float] = Field(None, alias="Properties", description="Total properties owned")
    purchase_of_business: Optional[float] = Field(None, alias="Purchase Of Business",
                                                  description="Cash outflow for business acquisitions")
    purchase_of_investment: Optional[float] = Field(None, alias="Purchase Of Investment",
                                                    description="Cash outflow for investment purchases")
    purchase_of_ppe: Optional[float] = Field(None, alias="Purchase Of PPE",
                                             description="Cash outflow for purchases of property, plant, and equipment")
    raw_materials: Optional[float] = Field(None, alias="Raw Materials", description="Inventory of raw materials")
    receivables: Optional[float] = Field(None, alias="Receivables", description="Total receivables")
    reconciled_cost_of_revenue: Optional[float] = Field(None, alias="Reconciled Cost Of Revenue",
                                                        description="Reconciled cost of revenue")
    reconciled_depreciation: Optional[float] = Field(None, alias="Reconciled Depreciation",
                                                     description="Reconciled depreciation expense")
    repayment_of_debt: Optional[float] = Field(None, alias="Repayment Of Debt",
                                               description="Cash outflow for debt repayments")
    repurchase_of_capital_stock: Optional[float] = Field(None, alias="Repurchase Of Capital Stock",
                                                         description="Cash outflow for repurchase of capital stock")
    research_and_development: Optional[float] = Field(None, alias="Research And Development",
                                                      description="Total spending on R&D")
    retained_earnings: Optional[float] = Field(None, alias="Retained Earnings", description="Accumulated retained earnings")
    sale_of_investment: Optional[float] = Field(None, alias="Sale Of Investment",
                                                description="Proceeds from the sale of investments")
    selling_general_and_administration: Optional[float] = Field(None, alias="Selling General And Administration",
                                                                description="Total SG&A expenses")
    share_issued: Optional[float] = Field(None, alias="Share Issued", description="Total shares issued")
    stock_based_compensation: Optional[float] = Field(None, alias="Stock Based Compensation",
                                                      description="Total stock-based compensation expense")
    stockholders_equity: Optional[float] = Field(None, alias="Stockholders Equity", description="Total stockholders' equity")
    tangible_book_value: Optional[float] = Field(None, alias="Tangible Book Value",
                                                 description="Book value of tangible assets")
    tax_effect_of_unusual_items: Optional[float] = Field(None, alias="Tax Effect Of Unusual Items",
                                                         description="Tax effects of unusual items")
    tax_provision: Optional[float] = Field(None, alias="Tax Provision", description="Provision for taxes")
    tax_rate_for_calcs: Optional[float] = Field(None, alias="Tax Rate For Calcs",
                                                description="Effective tax rate used for calculations")
    total_assets: Optional[float] = Field(None, alias="Total Assets", description="Total assets held by the company")
    total_capitalization: Optional[float] = Field(None, alias="Total Capitalization", description="Total capitalization")
    total_debt: Optional[float] = Field(None, alias="Total Debt", description="Total debt obligations")
    total_equity_gross_minority_interest: Optional[float] = Field(None, alias="Total Equity Gross Minority Interest",
                                                                  description="Total equity including gross minority interest")
    total_expenses: Optional[float] = Field(None, alias="Total Expenses", description="Total expenses incurred")
    total_liabilities_net_minority_interest: Optional[float] = Field(None, alias="Total Liabilities Net Minority Interest",
                                                                     description="Total liabilities excluding minority interest")
    total_non_current_assets: Optional[float] = Field(None, alias="Total Non Current Assets",
                                                      description="Total assets that are non-current")
    total_non_current_liabilities_net_minority_interest: Optional[float] = Field(None,
        alias="Total Non Current Liabilities Net Minority Interest",
        description="Total non-current liabilities excluding minority interest")
    total_operating_income_as_reported: Optional[float] = Field(None, alias="Total Operating Income As Reported",
                                                                description="Total operating income as reported")
    total_revenue: Optional[float] = Field(None, alias="Total Revenue", description="Total revenue generated")
    total_tax_payable: Optional[float] = Field(None, alias="Total Tax Payable", description="Total tax payable")
    trade_and_other_payables_non_current: Optional[float] = Field(None, alias="Tradeand Other Payables Non Current",
                                                                  description="Trade and other non-current payables")
    treasury_shares_number: Optional[float] = Field(None, alias="Treasury Shares Number",
                                                    description="Number of treasury shares held")
    working_capital: Optional[float] = Field(None, alias="Working Capital",
                                             description="Working capital available to the company")


def combine_duplicates(data: pd.DataFrame) -> pd.Series:
    column = data.T.columns[0]
    if data.T.shape[-1]>1:
        new_data = data.T.max(skipna=True, axis=1)

        return new_data
    return data.T[column]

class Financials(BaseFinancials):
    date: datetime
    symbol: str

class ManyFinancials(BaseModel):
    financials: List[Financials]

    @classmethod
    def from_yfinance(cls, equity: "Equity") ->"ManyFinancials":
        ticker = yf.Ticker(equity.symbol)
        data = pd.concat(
            [
                ticker.incomestmt.T,
                ticker.balancesheet.T,
                ticker.cashflow.T,
                ticker.financials.T,
                ticker.quarterly_balancesheet.T
            ],
            axis=1,
        )
        data_ = pd.DataFrame([equity.symbol] * len(data), columns=["symbol"], index=data.index)
        data = pd.concat([data, data_], axis=1)
        data = data.T.groupby(data.columns).apply(combine_duplicates).T
        data = data.reset_index(names="date")
        records = data.to_dict(orient="records")
        return  cls(financials=[Financials(**record) for record in records])

    def write(self, database: "BearishDb"):
        database.write_financials(self.financials)

if __name__ == "__main__":
    from bearish.database.crud import BearishDb
    from bearish.equities import Equity
    from bearish.equities import Equity, EquityQuery

    bearish_db = BearishDb()
    # equities = Equities.from_url()
    # equities.write(bearish_db)
    equities = bearish_db.read_equities(EquityQuery(countries=["Belgium"], exchanges=["BRU"]))
    for equity in equities:
        financials = ManyFinancials.from_yfinance(equity)
        financials.write(bearish_db)
