# encoding: utf-8
from __future__ import absolute_import, unicode_literals

from apiview.views import ViewSite
from dingtalk.core.constants import SuitePushType
from django.forms import fields
from django.utils.encoding import force_text
from rest_framework.response import Response

from core import view
from . import models, constants


site = ViewSite(name='dingtalk', app_name='apps.dingtalk')


@site
class SuiteCallback(view.APIBase):

    name = '授权事件接收URL'

    def proc_message(self, suite_key, message):
        event_type = message.get('EventType', None)
        ret = 'success'
        if event_type in (SuitePushType.CHECK_CREATE_SUITE_URL, SuitePushType.CHECK_UPDATE_SUITE_URL):
            ret = message.get('Random', '')
        elif event_type == SuitePushType.TMP_AUTH_CODE:
            permanent_code_data = message.get('__permanent_code_data', {})
            auth_corp_info = permanent_code_data.get('permanent_code_data', {})
            permanent_code = permanent_code_data.get('permanent_code', None)
            ch_permanent_code = permanent_code_data.get('ch_permanent_code', None)
            corpid = auth_corp_info.get('corpid', None)
            corp_name = auth_corp_info.get('corp_name', None)
            if permanent_code is None or corpid is None or corp_name is None:
                ret = 'fail'
            else:
                corp = models.Corp.objects.get_all_queryset().filter(suite_id=suite_key, corpid=corpid).first()
                if corp is None:
                    corp = models.Corp()
                    corp.suite_id = suite_key
                    corp.corpid = corpid
                corp.permanent_code = permanent_code
                if ch_permanent_code is not None:
                    corp.ch_permanent_code = ch_permanent_code
                corp.corp_name = corp_name
                corp.status = constants.CORP_STSTUS_CODE.AUTH.code
                corp.save_or_update()
        elif event_type == SuitePushType.CHANGE_AUTH:
            pass

        elif event_type == SuitePushType.SUITE_RELIEVE:
            corp_id = message.get('AuthCorpId', None)
            if corp_id is None:
                ret = 'fail'
            else:
                corp = models.Corp.objects.get_all_queryset().filter(corpid=corp_id, suite_id=suite_key).first()
                if corp is not None:
                    corp.status = constants.CORP_STSTUS_CODE.NO.code
                    corp.save_changed()
        elif event_type == SuitePushType.CHECK_SUITE_LICENSE_CODE:
            pass
        elif event_type != SuitePushType.SUITE_TICKET:
            self.logger.warning("unkown event_type : %s %s", suite_key, message)
        return ret

    def get_context(self, request, suite_key=None, *args, **kwargs):
        self.logger.info("receive_ticket msg path: %s query: %s, body: %s",
                         request.path, request.META['QUERY_STRING'], self.get_req_body(request))
        msg = self.get_req_body(request)
        assert msg
        msg = force_text(msg)
        suite = models.Suite.objects.filter(suite_key=suite_key).first()
        assert suite
        client = suite.get_suite_client()
        message = client.parse_message(msg, request.params.signature, request.params.timestamp, request.params.nonce)
        self.logger.info("receive_ticket msg: %s" % force_text(message))

        return Response(client.crypto.encrypt_message(self.proc_message(suite_key, message)))

    class Meta:
        path = "suite/callback/(?P<suite_key>[0-9a-zA-Z]+)"
        param_fields = (
            ('timestamp', fields.CharField(help_text='timestamp', required=True)),
            ('nonce', fields.CharField(help_text='nonce', required=True)),
            ('signature', fields.CharField(help_text='signature', required=True))
        )


urlpatterns = site.urlpatterns
