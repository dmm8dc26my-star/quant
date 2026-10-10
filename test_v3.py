import numpy as np
import pandas as pd
from v3_intelligence import _features,train_price_model

def test_features_and_model_guard():
    s=pd.Series(100*np.exp(np.arange(300)*.001),index=pd.bdate_range('2020-01-01',periods=300))
    assert len(_features(s,299))==4
    assert train_price_model({'AAPL':s},min_training=100)['status']=='insufficient_samples'
