# -*- coding: utf-8 -*-
import json
import logging
import urllib
import urllib2

import webapp2

# Secrets should have a slack_bot_token (which is actually a user's API token)
# and a set tokens of valid string slash command tokens.
# TODO(benkraft): for stupid reasons, this currently has to be a user's slack
# API token, not a bot's, because slack doesn't allow us to use the relevant
# APIs.  generate a properly-scoped OAuth token or something.
# TODO(benkraft): store secrets in datastore so it's easy to add more commands
# (or teams!)
import secrets

_SLACK_API_URL = 'https://slack.com/api/'


def hit_slack_api(method, data=None):
    if data is None:
        data = {}
    data['token'] = secrets.slack_bot_token
    data['as_user'] = True
    res = urllib2.urlopen(_SLACK_API_URL + method,
                          data=urllib.urlencode(data))
    decoded = json.loads(res.read())
    if not decoded['ok']:
        raise RuntimeError("not ok, slack said %s" % decoded)
    return decoded


def get_user_id(username):
    """Username without @.  Returns slack ID (UXXXXXXX), or None."""
    users = hit_slack_api('users.list')['members']
    for user in users:
        if user['name'] == username:
            return user['id']


def get_profile_field_infos():
    return hit_slack_api('team.profile.get')['profile']['fields']


def get_profile_field(user_id, field):
    """Field is slash-separated, e.g. "email" or "fields/Xxxxxxxx"."""
    data = hit_slack_api('users.profile.get',
                         {'user': user_id, 'include_labels': 1})['profile']
    logging.debug("profile data %s" % data)
    for key in field.split('/'):
        # NOTE: If the user hasn't filled any custom fields, "fields" will be
        # null instead of [].
        if data.get(key):
            data = data[key]
        else:
            return None  # Caller must determine why.
    return data


def get_full_answer(username, field):
    try:
        user_id = get_user_id(username.strip("@"))
        logging.debug("user ID %s" % user_id)
        if not user_id:
            return "No user '%s' found." % username
        field_data = get_profile_field(user_id, field)
        logging.debug("field data %s" % field_data)
        if isinstance(field_data, dict):
            # Custom fields are dicts with labels (since we asked for them) and
            # values.  The labels tend to be title-cased.
            return "%s's %s is %s." % (
                username, field_data['label'].lower(), field_data['value'])
        elif field_data:
            # Builtin fields are just values.
            return "%s's %s is %s." % (username, field, field_data)
        elif field_data == "":
            # Builtin fields are blank if unset.
            return "%s has not listed a %s." % (
                username, field)
        elif field.startswith('fields/'):
            # Custom fields are omitted if not defined, so see if it exists.
            field_id = field.split('/')[1]
            field_infos = get_profile_field_infos()
            logging.debug("field info %s" % field_infos)
            for field_info in field_infos:
                if field_info['id'] == field_id:
                    return "%s has not listed a %s." % (
                        username, field_info['label'].lower())
        else:
            return "Not a valid profile field."
    except BaseException as e:
        logging.exception(e)
        return "Something went wrong."


class Profile(webapp2.RequestHandler):
    def post(self, field):
        """The field path (slash-separated) is the request path.

        For example, email is at /email, and custom fields are at
        /fields/Xxxxxxxxx.

        TODO(benkraft): allow specifying fields by name?
        """
        token = self.request.get('token')
        if token not in secrets.tokens:
            logging.info("Invalid token %s" % token)
            self.response.write("Unauthorized.")
            self.response.set_status(401)
            return

        logging.debug("request %s" % self.request)
        text = self.request.get('text')
        if not text or ' ' in text:
            self.response.write("Usage: /<command> <username>.")
            return

        self.response.write(get_full_answer(text, field))


app = webapp2.WSGIApplication([
    ('/(.*)', Profile),
])
