## FEMS Real-time Weather
## Summarize precip obs and forecasts by station for Southwest MT zone
### Written by: W. Matt Jolly
### Version: 0.1 alpha
### Date:  12 May 2026

import pandas as pd
import requests
from datetime import date, timedelta

def GetFiltered(df,ndays,refdatetime = pd.Timestamp.now(), plus=False):
    # Filter for either historical times (minus) or future times (plus)
    if not plus:
        cutoff = refdatetime- pd.Timedelta(days=ndays)
        filtered_df = df[df['DateTime'] >= cutoff]
    else:
        cutoff = refdatetime + pd.Timedelta(days=ndays)
        filtered_df = df[df['DateTime'] <= cutoff]
 
    return filtered_df

# Get today's date
today = date.today()

# Calculate relative dates
thirty_days_ago = today - timedelta(days=30)
seven_days_ahead = today + timedelta(days=7)
femsurl = 'https://fems.fs2c.usda.gov/api/ext-climatology/download-wx-daily-summary/'
stnlist = '241513,241520,242902,242911,243004,101019,241211,241404,242914,241507,241405,241206,241519,241403,242915,241508,244403'
url = f'{femsurl}?stationIds={stnlist}&startDate={thirty_days_ago}&endDate={seven_days_ahead}&dataset=all&dataFormat=csv'
print(url)
response = requests.get(url)

# Open the local file in 'write binary' mode
with open('Data/wx_file.csv', 'wb') as file:
    file.write(response.content)

df = pd.read_csv('Data/wx_file.csv')
df['DateTime'] = pd.to_datetime(df.Date)

df_o =  df[(df.ObservationType == "O")]
df_f =  df[(df.ObservationType == "F")]

filtered_2d_df = GetFiltered(df_o,2)
filtered_5d_df = GetFiltered(df_o,5)
filtered_7d_df = GetFiltered(df_o,7)
filtered_10d_df = GetFiltered(df_o,10)
filtered_30d_df = GetFiltered(df_o,30)
filtered_2dfx_df = GetFiltered(df_f,1,plus=True)
filtered_5dfx_df = GetFiltered(df_f,4,plus=True)
filtered_7dfx_df = GetFiltered(df_f,6,plus=True)

df_o_2_pt = pd.pivot_table(filtered_2d_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Obs Precip 48 hr(in)'})
df_o_5_pt = pd.pivot_table(filtered_5d_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Obs Precip 5 day(in)'})
df_o_7_pt = pd.pivot_table(filtered_7d_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Obs Precip 7 day(in)'})
df_o_10_pt = pd.pivot_table(filtered_10d_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Obs Precip 10 day(in)'})
df_o_30_pt = pd.pivot_table(filtered_30d_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Obs Precip 30 day(in)'})
df_f_2_pt = pd.pivot_table(filtered_2dfx_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Fcst Precip 48 hr(in)'})
df_f_5_pt = pd.pivot_table(filtered_5dfx_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Fcst Precip 5 day(in)'})
df_f_7_pt = pd.pivot_table(filtered_7dfx_df, values='Precipitation24hr(in)', index='StationName', aggfunc='sum', fill_value=0).rename(columns={'Precipitation24hr(in)':'Fcst Precip 7 day(in)'})

prcp_table = pd.concat([df_f_5_pt,df_f_2_pt,df_o_2_pt,df_o_5_pt,df_o_7_pt,df_o_10_pt,df_o_30_pt],axis=1)
prcp_table = prcp_table.round(3)
prcp_table['Date'] = date.today().strftime("%Y-%m-%d")
col_to_move = prcp_table.pop("Date")
prcp_table.insert(0, "Date", col_to_move)
prcp_table.to_csv('Tables/swmt_zone_precip_summary.csv')