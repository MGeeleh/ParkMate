import datetime
import json
import requests
from flask import Flask, render_template, request, url_for, redirect, session
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import pandas as pd
from datetime import datetime, timedelta
from pytz import timezone, all_timezones
import plotly
import plotly.graph_objects as go
import plotly.express as px


application = Flask(__name__)
application.config['SECRET_KEY'] = ""

@application.route('/', methods=['POST', 'GET'])
def root():
    if request.method == 'POST':
        email = request.form["umail"]
        password = request.form["password"]
        login = requests.get(
            "LOGIN ENPOINT HERE" + email + "&password=" + password)
        loginJSON = login.json()
        if loginJSON['auth'] == 1:
            userData = requests.get(
                "GET USER ENPOINT HERE" + email)
            userJSON = userData.json()
            session['email'] = userJSON["details"]["email"]
            session['first_name'] = userJSON["details"]["first_name"]
            session['last_name'] = userJSON["details"]["last_name"]
            session['password'] = userJSON["details"]["password"]
            session['image_url'] = userJSON["details"]["image_url"]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error_msg=loginJSON['message'])
    else:
        return render_template('login.html')


@application.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        email = request.form["umail"]
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        password = request.form["password"]
        print(first_name + last_name)
        register = requests.get("REGISTER ENDPOINT HERE" + email + "&password=" + password)
        registerJSON = register.json()
        print(registerJSON['auth'])
        if registerJSON['auth'] == 1:
            response = requests.get("CREATE USER ENDPOINT" + email + "&first_name=" + first_name + "&last_name=" + last_name + "&password=" + password)
            print(response.text)
            return redirect(url_for('root'))
        else:
            return render_template('register.html', error_msg=registerJSON['message'])
    else:
        return render_template('register.html')


@application.route('/home', methods=['POST', 'GET'])
def home():
    x = requests.get('PARKING SPACE DATA URL HERE')
    bays = x.json()
    baysn = []
    for bay in bays:
        location = bay["location"]
        newBay = [bay['bay_id'], location["latitude"], location["longitude"]]
        baysn.append(newBay)
    # Get the current temp and description
    weather = requests.get("https://api.openweathermap.org/data/2.5/weather?q=Melbourne,%20AU&appid=WEATHERAPIHERE&units=metric")
    weatherJSON  = weather.json()
    weather_desc = weatherJSON['weather'][0]['description']
    weather = weatherJSON['main']['temp']
    return render_template('home.html', bays=baysn, numOfBays=len(baysn), weather_desc = weather_desc, weather = weather,
                           first_name = session['first_name'], img_url=session['image_url'])


@application.route('/bay', methods=['POST', 'GET'])
def bayp():
    bayid = request.args.get('bayid', None)
    baylat = request.args.get('baylat', None)
    baylon = request.args.get('baylon', None)
    print(bayid)
    print(baylat)
    print(baylon)
    graphJSON, parking_status = plot_graph(bayid)
    return render_template('bay.html', bayid=bayid, baylat=baylat, baylon=baylon, graphJSON=graphJSON, parking_status=parking_status)


@application.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('root'))


@application.route('/redirecthome', methods=['POST', 'GET'])
def redirecthome():
    return redirect(url_for('home'))




def plot_graph(bayid):

    data = get_status(bayid)
    current_status = "Not available at " if data["status"].iloc[-1] == "Present" else "Available at "
    xinterval = 1
    data['datetime'] = pd.to_datetime(data['datetime'], format='%Y-%m-%d %H:%M')
    start = data["datetime"].iloc[0] - timedelta(hours=1)
    end = data["datetime"].iloc[-1]
    # + timedelta(hours=0.5)
    xaxis_range = [dt.strftime('%Y-%m-%d %H:%M') for dt in datetime_range(start, end, timedelta(minutes=xinterval))]
    list_unoccupied = [ts.strftime('%Y-%m-%d %H:%M') for ts in
                       list(data[data['status'] == "Unoccupied"]['datetime'])]

    fig = go.Figure(layout=dict(height=250, plot_bgcolor='rgb(255,255,255)'))

    fig.add_trace(go.Scatter(
        x=xaxis_range, y=[0] * len(xaxis_range),
        mode='markers',
        marker=dict(color='lightcoral', size=40, line=dict(color='lightcoral', width=6,), symbol="42")
        # marker_color="lightcoral",
    ))
    fig.add_trace(go.Scatter(
        x=list_unoccupied, y=[0] * len(list_unoccupied),
        mode='markers',
        marker=dict(color='aquamarine', size=40, line=dict(color='aquamarine', width=6, ), symbol="42")
        # marker_color="aquamarine"
    ))
    # colorxrange = ["aquamarine" if ts in list_unoccupied else "lightcoral" for ts in xaxis_range]
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(visible=False, showticklabels=False, showgrid=False)
    fig.update_layout(showlegend=False,title="Parking Availability for bayid " + bayid, title_x=0.5)

    # fig.update_traces(marker_size=40, marker_symbol="line-ns", marker_line_width=6, marker_line_color=colorxrange)

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON, current_status + data["datetime"].iloc[-1].strftime('%H:%M')


def datetime_range(start, end, delta):
    current = start
    while current < end:
        yield current
        current += delta


def get_status(bayid):
    # dynamodb = boto3.resource('dynamodb')

    dynamodb = boto3.resource('dynamodb',
                              region_name='us-east-1')

    subset_df = pd.DataFrame()
    isEmpty = True
    table = dynamodb.Table('parking_sensor')
    response = table.query(KeyConditionExpression=Key('bayid').eq(str(bayid)))

    # print(type(response), response)
    # converting dict to dataframe
    result_df = pd.DataFrame.from_dict(response['Items'])

    return result_df

if __name__ == '__main__':
    application.run(host='127.0.0.1', port=8080, debug=True)
