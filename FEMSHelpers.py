import requests, json, bisect
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import geopandas as gpd
from datetime import datetime,timedelta
import contextily as cx

col1 = '#d53e4f'  # Red
col2 = '#fc8d59'
col3 = '#fee08b'
col4 = '#ffffbf'  # Yellow
col5 = '#e6f598'
col6 = '#99d594'
col7 = '#3288bd'  # Blue

# Grab the real-time data for FEMS
def GetRTFEMSData(sta_id,client,query):
    #sta_id = str("241513,241507,241508")
    #sta_id = str("241513")
    currYear = datetime.now().year
    myStartDateTxt = f"{currYear}-01-01"
    myEndDateTxt = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    params = {"stationIds": sta_id,"FuelModels": "Y","StartDate":myStartDateTxt,"EndDate":myEndDateTxt}
    result = client.execute_sync(query,variable_values=params)
    return(result)

def GetStationID(row):
    match row['stationName']:
        case "NINE MILE":
            return 241507
        case "SEELEY LAKE":
            return 251508
        case "BLUE MTN":
            return 241513
        case "ST. REGIS":
            return 241302
        case "PLAINS":
            return 241206
        case "RONAN":
            return 241403
        case _: # The wildcard case, similar to 'default' in other languages
            return "UNKOWN"
def MakeFEMSWXDataframe(result):
    results = json.dumps(result)
    # parse x:
    wxobs = json.loads(str(results))
    vals = wxobs['weatherObs']['data']
    temp = []
    rh = []
    date = []
    for wxob in wxobs['weatherObs']['data'][:]:
        temp.append(float(wxob['temperature']))
        rh.append(float(wxob['relative_humidity']))
        date.append(pd.to_datetime(wxob['observation_time']))
    df = pd.DataFrame(
    {'DateTime': date,
     'Temperature': temp,
     'RH': rh
    })
    return df

## Functiont to retrieve the FEMS station list and create a GeoDataFrame
def MakeFEMSWXStationDataframe(client):
    query = gql("""query Stations { stationMetaData(returnAll: true) { data { station_id latitude longitude agency}}}""")
    # Execute the query on the transport
    result = client.execute_sync(query)
    results = json.dumps(result)
    stations = json.loads(str(results))
    lats = []
    lons = []
    stationids = []
    agencys = []
    
    for station in stations['stationMetaData']['data'][:]:
        stationids.append(station['station_id'])
        lats.append(float(station['latitude']))
        lons.append(float(station['longitude']))
        agencys.append(station['agency'])
        
        df = pd.DataFrame({"StationID": [station['station_id']],"Latitude": [station['latitude']], "Longitude": [station['longitude']],"Agency": [station['agency']]})
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude), crs="EPSG:4326")
        
    df = pd.DataFrame({"StationID": stationids,"Latitude": lats, "Longitude": lons,"Agency":agencys})
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude), crs="EPSG:4326")
    return gdf


def MakeFEMSNFDRSDataframe(result):
    results = json.dumps(result)
    # parse x:
    wxobs = json.loads(str(results))
    vals = wxobs['nfdrsObs']['data']
    stationid = []
    fuelmodel = []
    obstype = []
    onehr = []
    tenhr = []
    hundhr = []
    thouhr = []
    woodyfm = []
    kbdi = []
    erc = []
    bi = []
    date = []
    i = 0
    for wxob in wxobs['nfdrsObs']['data'][:]:
        fuelmodel.append(wxob['fuel_model'])
        
        stationid.append(wxob['station_id'])
        
        onehr.append(float(wxob['one_hr_tl_fuel_moisture']))
        tenhr.append(float(wxob['ten_hr_tl_fuel_moisture']))
        hundhr.append(float(wxob['hun_hr_tl_fuel_moisture']))
        thouhr.append(float(wxob['thou_hr_tl_fuel_moisture']))
        woodyfm.append(float(wxob['woody_lfi_fuel_moisture']))
        erc.append(float(wxob['energy_release_component']))
        bi.append(float(wxob['burning_index']))
        kbdi.append(float(wxob['kbdi']))
        obstype.append(wxob['nfdr_type'])
        date.append(pd.to_datetime(wxob['observation_time']))
    df = pd.DataFrame({'StationID':stationid,'FuelModel':fuelmodel,'DateTime': date, 'ObsType':obstype,'MC1': onehr,'MC10': tenhr, 'MC100':hundhr,'MC1000':thouhr,'ERC': erc, 'BI':bi,'WOOD':woodyfm })
    return df

def BuildNFDRSHist(filelist):
    dfout = pd.DataFrame()
    for f in filelist:
        dfin = pd.read_csv(f)
        dfin['StationID'] = dfin.apply(GetStationID, axis=1)
        dfout = pd.concat([dfout,dfin])
    dfout['DateTime'] = pd.to_datetime(dfout.observationTime)
    dfout = dfout.sort_values(by='DateTime')
    
    return dfout

## Summarize the hourly data files up to daily max/mins as appropriate
def SummarizeDaily(df_hist):
    
    df_hist.set_index('DateTime',inplace=True)
    # Resample to daily max and mins
    df_hist_max = df_hist.resample("1D").max()
    df_hist_min = df_hist.resample("1D").min()
    df_hist.reset_index(inplace=True)
    df_hist_max.reset_index(inplace=True)
    df_hist_min.reset_index(inplace=True)
    
    # Groupby date to get a daily mean
    df_hist_mn_erc = df_hist.groupby(df_hist.DateTime.dt.date).energyReleaseComponent.mean()
    df_hist_mn_bi = df_hist.groupby(df_hist.DateTime.dt.date).burningIndex.mean()
    
    df_out = pd.DataFrame() 
    df_out['DateTime'] = df_hist_min.DateTime
    df_out['MC1DailyMin'] = df_hist_min.oneHR_TL_FuelMoisture
    df_out['MC10DailyMin'] = df_hist_min.tenHR_TL_FuelMoisture
    df_out['MC100DailyMin'] = df_hist_min.hundredHR_TL_FuelMoisture
    df_out['MC1000DailyMin'] = df_hist_min.thousandHR_TL_FuelMoisture
    df_out['MCHERBDailyMin'] = df_hist_min.herbaceousLFI_fuelMoisture
    df_out['MCWOODDailyMin'] = df_hist_min.woodyLFI_fuelMoisture
    
    df_out['ERCDailyMax'] = df_hist_max.energyReleaseComponent
    df_out['BIDailyMax'] = df_hist_max.burningIndex
    
    return df_out



def MakePlot(df, df_hist,sta_ids,title,var,year,date,percs=[],fuelModel="Y",oFile=""):
    
    df = df[(df.DateTime >= f'01-01-{year}') & (df.DateTime <= f'12-31-{year}')]

    # Grab the most recent "O" types
    RecentERCPerc = df[(df.ObsType == "O")].iloc[[-1]]['ERCDailyMaxPerc'].round(1).values
    RecentBIPerc = df[(df.ObsType == "O")].iloc[[-1]]['BIDailyMaxPerc'].round(1).values
    RecentERC = df[(df.ObsType == "O")].iloc[[-1]]['ERC'].round(1).values
    RecentBI = df[(df.ObsType == "O")].iloc[[-1]]['BI'].round(1).values
    
    f,ax = plt.subplots()
    currPerc = ""
    # Define Products and Product Labels for maps
    Flip = False
    if var == "ERC":
        mvar = "ERCDailyMax"
        label = f"Energy Release Component (ERC)\n(Fuel Model {fuelModel}"
        currPerc = RecentERCPerc
    elif var == "BI":
        mvar = "BIDailyMax"
        label = f"Burning Index (BI)\n(Fuel Model {fuelModel}"
        currPerc = RecentBIPerc
    elif var == "MC1000":
        mvar = "MC1000DailyMin"
        label = f"1000-hr Fuel Moisture (%)"
        Flip = True
    elif var == "MC100":
        mvar = "MC100DailyMin"
        label = f"100-hr Fuel Moisture (%)"
        Flip = True
        
    # Plot the climatology
    df_hist[45:].groupby(df_hist.DateTime.dt.dayofyear)[mvar].max().plot(color=col1,rot=45,ax=ax,label='Max',legend=True,linewidth=0.75)
    df_hist[45:].groupby(df_hist.DateTime.dt.dayofyear)[mvar].mean().plot(color='grey',rot=45,ax=ax,label='Avg',legend=True,linewidth=0.75)
    df_hist[45:].groupby(df_hist.DateTime.dt.dayofyear)[mvar].min().plot(color=col7,rot=45,ax=ax,label='Min',legend=True,linewidth=0.75)

    # Plot the current values
    
    if var == "ERC" or var == "BI":
        currentLabel = f"{var}: {df[(df.ObsType == "O")].iloc[[-1]][var].round(1).values[0]} ({currPerc[0]}%)"
    else:
        currentLabel = f"{year}"
    df[(df.ObsType == "O")].iloc[[-1]][var].to_frame(name='Current').reset_index().plot.scatter(x='index',y='Current',ax=ax,c=col2,label=f"Current {currentLabel}")
    df[df.ObsType=="O"].groupby(df.DateTime.dt.dayofyear)[var].mean().plot(color=col2,ax=ax,rot=45,label= f"{var} ({year})",legend=True,linewidth=2)
    df[df.ObsType=="F"].groupby(df.DateTime.dt.dayofyear)[var].mean().plot(color=col2,ax=ax,rot=45,label="Forecast",legend=True,linestyle=':',linewidth=2)
   
    
    # Set the axis and plot a grid
    ax.set_axisbelow(True)
    ax.grid(True)

    # Make the plot pretty and informative
    ax.set_title(f"{sta_ids}")
    ax.set_xlabel("Yearday Date")
    ax.set_xlim([1,365])
    ax.set_ylabel(label)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1)) 
    # Use DateFormatter to format the labels as abbreviated month names (%b)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    if not Flip:
        perclow = df_hist[mvar].quantile([0.90]).round(1).values[0]
        perclowlabel = "90th Percentile"
        perchigh = df_hist[mvar].quantile([0.97]).round(1).values[0]
        perchighlabel = "97th Percentile"
    else:
        perclow = df_hist[mvar].quantile([0.10]).round(1).values[0]
        perclowlabel = "10th Percentile"
        perchigh = df_hist[mvar].quantile([0.03]).round(1).values[0]
        perchighlabel = "3rd Percentile"
        
    #if len(percs) > 0:
    ax.axhline(perclow,color='black',linestyle='--',label=f'{perclowlabel} ({perclow})')
    ax.axhline(perchigh,color='black',linestyle='-.',label=f'{perchighlabel} ({perchigh})')        
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5)) 
    f.suptitle(f'{title} ({date})')
    if oFile != "":
        plt.savefig(oFile,bbox_inches='tight') 



def BuildSingleNFDRSHist(singlefilenm,myFuelModel = "Y"):
    dfout = pd.read_csv(singlefilenm)
    dfout['DateTime'] = pd.to_datetime(dfout.observationTime)
    dfout = dfout.sort_values(by='DateTime')
    dfout = dfout[dfout.fuelModelType == myFuelModel]
    return dfout

def MakeRAWSMap(gdfStations, station_list,xlim=[45,49],ylim=[-115,-113]):
    f,ax = plt.subplots(figsize=[8,8])
    gdfStations[gdfStations.StationID.isin(station_list)].plot(ax=ax)
    #ax.set_ylim(ylim)
    #ax.set_xlim(xlim)
    cx.add_basemap(ax, crs=gdfStations.crs)

def FilterDates(df,myStartDate,myEndDate):
    return df[(df.DateTime >= myStartDate) &(df.DateTime <= myEndDate)]
    
# Look up percentile classes
def LookupClass(myVal,myBreakpoints):
    # bisect_left returns the insertion point to maintain order
    index = bisect.bisect_left(myBreakpoints, myVal)
    return index


# Lookup the combined DRL class
def LookupDRLClass(x, y, matrix):
    # Returns class at x (column) and y (row)
    # Using [row, col] format
    return matrix[y, x]


## Summarize the hourly data files up to daily max/mins as appropriate
def SummarizeDaily(df_hist):
    df_hist['DateTime'] = pd.to_datetime(df_hist['observationTime'])
    df_hist.set_index('DateTime',inplace=True)
    # Resample to daily max and mins
    df_hist_max = df_hist.groupby('stationName').resample("1D").max().reset_index(drop=True)
    df_hist_max['DateTime'] = pd.to_datetime(df_hist_max['observationTime'])
    df_hist_max.set_index('DateTime',inplace=True)
    
    df_hist_min = df_hist.groupby('stationName').resample("1D").min().reset_index(drop=True)
    df_hist_min['DateTime'] = pd.to_datetime(df_hist_min['observationTime'])
    df_hist_min.set_index('DateTime',inplace=True)
    
       
    df_out = pd.DataFrame() 
    df_out['DateTime'] = df_hist_min.resample("1D").observationTime.min()
    df_out['MC1DailyMin'] = df_hist_min.resample("1D").oneHR_TL_FuelMoisture.mean()
    df_out['MC10DailyMin'] = df_hist_min.resample("1D").tenHR_TL_FuelMoisture.mean()
    df_out['MC100DailyMin'] = df_hist_min.resample("1D").hundredHR_TL_FuelMoisture.mean()
    df_out['MC1000DailyMin'] = df_hist_min.resample("1D").thousandHR_TL_FuelMoisture.mean()
    df_out['MCHERBDailyMin'] = df_hist_min.resample("1D").herbaceousLFI_fuelMoisture.mean()
    df_out['MCWOODDailyMin'] = df_hist_min.resample("1D").woodyLFI_fuelMoisture.mean()
    
    df_out['ERCDailyMax'] = df_hist_max.resample("1D").energyReleaseComponent.mean()
    df_out['BIDailyMax'] = df_hist_max.resample("1D").burningIndex.mean()
    
    return df_out

def CalcHistPercs(df):
    df['ERCPerc'] = df.ERCDailyMax.rank(pct=True)
    df['BIPerc'] = df.BIDailyMax.rank(pct=True)
    df['SFDIPerc'] = df['ERCPerc'] * df['BIPerc']
    sfdi_breaks = df['SFDIPerc'].quantile([0.6,0.8,0.9,0.97])
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    return df,sfdi_breaks

def SFDIClassToText(val):
    if val == 0:
        return "Low"
    elif val == 1:
        return "Mod"
    elif val == 2:
        return "High"
    elif val == 3:
        return "Very High"
    elif val == 4:
        return "Severe"
    else:
        return "Unknown"

def BIClassToText(val):
    if val == 0:
        return "Low"
    elif val == 1:
        return "Mod"
    elif val == 2:
        return "High"
    else:
        return "Unknown"

def ERCClassToText(val):
    if val == 0:
        return "Low"
    elif val == 1:
        return "Mod"
    elif val == 2:
        return "High"
    elif val == 3:
        return "Very High"
    elif val == 4:
        return "Extreme"
    else:
        return "Unknown"

def IterateFigures(units, variables,year,todayStr):
    for unit in units:
        for variable in variables:
            
            # Create the output plot file name
            oFile = f'{unit['oFileBasePath']}{variable}_current.png'
            if variable in unit['Percs']:
                percs = unit['Percs'][variable]
                MakePlot(unit['rt_df'],unit['hist_df'],unit['sta_list'],unit['title'],variable,year,todayStr,percs=percs,oFile=oFile)
            else:
                MakePlot(unit['rt_df'],unit['hist_df'],unit['sta_list'],unit['title'],variable,year,todayStr,oFile=oFile)

 # Grab the real-time data for FEMS
def GetRTFEMSData(sta_id,client, query, FuelModel="Y"):
    currYear = datetime.now().year
    myStartDateTxt = f"{currYear}-01-01"
    myEndDateTxt = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    params = {"stationIds": sta_id,"FuelModels": FuelModel,"StartDate":myStartDateTxt,"EndDate":myEndDateTxt}
    result = client.execute_sync(query,variable_values=params)
    return(result)
 
def SummarizeDailyRT(df):
    
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    df.set_index('DateTime',inplace=True)
    df_max = df[df.ObsType == "O"]
    df_max = df_max.groupby('StationID').resample("1D").max()
    df_o = df_max.droplevel('StationID').resample("1D")[['ERC','BI','MC1','MC10','MC100','MC1000','WOOD']].mean()
    df_o['ObsType'] = "O"
    
    df_max = df[df.ObsType == "F"]
    df_max = df_max.groupby('StationID').resample("1D").max()
    df_f = df_max.droplevel('StationID').resample("1D")[['ERC','BI','MC1','MC10','MC100','MC1000','WOOD']].mean()
    df_f['ObsType'] = "F"
    return pd.concat([df_o,df_f])
                 