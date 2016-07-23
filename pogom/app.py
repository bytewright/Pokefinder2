#!/usr/bin/python
# -*- coding: utf-8 -*-

import calendar
from flask import Flask, jsonify, render_template, request
from flask.json import JSONEncoder
from datetime import datetime
from s2sphere import *

from . import config
from .models import Pokemon, Gym, Pokestop, ScannedLocation


class Pogom(Flask):
    def __init__(self, import_name, args, **kwargs):
        super(Pogom, self).__init__(import_name, **kwargs)
        self.json_encoder = CustomJSONEncoder
        self.route("/", methods=['GET'])(self.fullmap)
        self.route("/raw_data", methods=['GET'])(self.raw_data)
        self.route("/loc", methods=['GET'])(self.loc)
        self.route("/next_loc", methods=['GET', 'POST'])(self.next_loc)
        self.route("/mobile", methods=['GET'])(self.list_pokemon)
        self.route("/locations", methods=['GET'])(self.get_saved_locations)
        self.setting = args

    def fullmap(self):
        return render_template('map.html',
                               lat=config['ORIGINAL_LATITUDE'],
                               lng=config['ORIGINAL_LONGITUDE'],
                               gmaps_key=config['GMAPS_KEY'],
                               lang=config['LOCALE'])

    def raw_data(self):
        d = {}
        if request.args.get('pokemon', 'true') == 'true':
            d['pokemons'] = Pokemon.get_active()

        if request.args.get('pokestops', 'false') == 'true':
            d['pokestops'] = Pokestop.get_all()

        if request.args.get('gyms', 'true') == 'true':
            d['gyms'] = Gym.get_all()

        if request.args.get('scanned', 'true') == 'true':
            d['scanned'] = ScannedLocation.get_recent()

        return jsonify(d)

    def loc(self):
        d = {}
        d['lat']=config['ORIGINAL_LATITUDE']
        d['lng']=config['ORIGINAL_LONGITUDE']

        return jsonify(d)

    def get_saved_locations(self):
        formatted_list = []
        for location in self.setting.locations:
            entry = {'latitude': location.split(',')[0], 'longitude': location.split(',')[1],
                     'name': location.split(',')[2]}
            formatted_list.append(entry)
        return render_template('locations.html', locations=formatted_list)

    def next_loc(self):
        if request.method == 'GET':
            return render_template('get_loc.html')
        if request.method == 'POST':
            if request.form['lat'] and request.form['lon']:
                lat = float(request.form['lat'])
                lon = float(request.form['lon'])
            else:
                lat = request.args.get('lat', type=float)
                lon = request.args.get('lon', type=float)
            if not (lat and lon):
                print('[-] Invalid next location: %s,%s' % (lat, lon))
                return 'bad parameters', 400
            else:
                config['ORIGINAL_LATITUDE'] = lat
                config['ORIGINAL_LONGITUDE'] = lon
                return 'ok'

    def list_pokemon(self):
        # todo: check if client is android/iOS/Desktop for geolink, currently only supports android
        pokemon_list = []
        pokemon_list_low = []
        origin_point = LatLng.from_degrees(config['ORIGINAL_LATITUDE'], config['ORIGINAL_LONGITUDE'])
        for pokemon in Pokemon.get_active():
            pokemon_point = LatLng.from_degrees(pokemon['latitude'], pokemon['longitude'])
            diff = pokemon_point - origin_point
            diff_lat = diff.lat().degrees
            diff_lng = diff.lng().degrees
            direction = (('N' if diff_lat >= 0 else 'S') if abs(diff_lat) > 1e-4 else '') + (
                ('E' if diff_lng >= 0 else 'W') if abs(diff_lng) > 1e-4 else '')
            entry = {
                'id': pokemon['pokemon_id'],
                'name': pokemon['pokemon_name'],
                'card_dir': direction,
                'distance': int(origin_point.get_distance(pokemon_point).radians * 6366468.241830914),
                'time_to_disappear': ('%02dm %02ds' % (divmod((pokemon['disappear_time']-datetime.utcnow()).seconds, 60))).replace('00m ', ''),
                'latitude': pokemon['latitude'],
                'longitude': pokemon['longitude']
            }
            if int(entry['distance']) > 1000:
                continue
            if entry['id'] in self.setting.ignore_pokemon:
                pokemon_list_low.append((entry, entry['distance']))
            else:
                pokemon_list.append((entry, entry['distance']))
        pokemon_list = [y[0] for y in sorted(pokemon_list, key=lambda x: x[1])]
        pokemon_list_low = [y[0] for y in sorted(pokemon_list_low, key=lambda x: x[1])]
        return render_template('mobile_list.html',
                               pokemon_list=pokemon_list,
                               pokemon_list_low=pokemon_list_low,
                               origin_lat=config['ORIGINAL_LATITUDE'],
                               origin_lng=config['ORIGINAL_LONGITUDE'])


class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                if obj.utcoffset() is not None:
                    obj = obj - obj.utcoffset()
                millis = int(
                    calendar.timegm(obj.timetuple()) * 1000 +
                    obj.microsecond / 1000
                )
                return millis
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)
