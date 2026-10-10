from universe_v4 import parse_directory

def test_nasdaq_excludes_etf_test_and_warrants():
    content='Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\nABC|ABC Common Stock|Q|N|N|100|N|N\nETF1|Index ETF|Q|N|N|100|Y|N\nTST|Test Company|Q|Y|N|100|N|N\nWRT|Warrant Company Warrant|Q|N|N|100|N|N\nFile Creation Time: 2026\n'
    assert parse_directory(content,'nasdaq')==[('ABC','ABC Common Stock')]

def test_otherlisted():
    content='ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\nXYZ|XYZ Common Stock|N|XYZ|N|100|N|XYZ\n'
    assert parse_directory(content,'other')==[('XYZ','XYZ Common Stock')]
