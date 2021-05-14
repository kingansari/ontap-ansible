# (c) 2018-2021, NetApp, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

''' unit test for ONTAP publickey Ansible module '''

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
import json
import pytest

from ansible.module_utils import basic
from ansible.module_utils._text import to_bytes
from ansible_collections.netapp.ontap.tests.unit.compat.mock import patch

from ansible_collections.netapp.ontap.plugins.modules.na_ontap_publickey \
    import NetAppOntapPublicKey as my_module, main as uut_main      # module under test


def set_module_args(args):
    """prepare arguments so that they will be picked up during module creation"""
    args = json.dumps({'ANSIBLE_MODULE_ARGS': args})
    basic._ANSIBLE_ARGS = to_bytes(args)  # pylint: disable=protected-access


class AnsibleExitJson(Exception):
    """Exception class to be raised by module.exit_json and caught by the test case"""


class AnsibleFailJson(Exception):
    """Exception class to be raised by module.fail_json and caught by the test case"""


def exit_json(*args, **kwargs):  # pylint: disable=unused-argument
    """function to patch over exit_json; package return data into an exception"""
    if 'changed' not in kwargs:
        kwargs['changed'] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):  # pylint: disable=unused-argument
    """function to patch over fail_json; package return data into an exception"""
    kwargs['failed'] = True
    raise AnsibleFailJson(kwargs)


WARNINGS = list()


def warn(dummy, msg):
    WARNINGS.append(msg)


def default_args():
    args = {
        'state': 'present',
        'hostname': '10.10.10.10',
        'username': 'admin',
        'https': 'true',
        'validate_certs': 'false',
        'password': 'password',
        'account': 'user123',
        'public_key': '161245ASDF',
        'vserver': 'vserver',
    }
    return args


# REST API canned responses when mocking send_request
SRR = {
    # common responses
    'is_rest': (200, dict(version=dict(generation=9, major=9, minor=0, full='dummy')), None),
    'is_rest_9_6': (200, dict(version=dict(generation=9, major=6, minor=0, full='dummy')), None),
    'is_rest_9_8': (200, dict(version=dict(generation=9, major=8, minor=0, full='dummy')), None),
    'is_zapi': (400, {}, "Unreachable"),
    'empty_good': (200, {}, None),
    'zero_record': (200, dict(records=[], num_records=0), None),
    'one_record_uuid': (200, dict(records=[dict(uuid='a1b2c3')], num_records=1), None),
    'end_of_sequence': (500, None, "Unexpected call to send_request"),
    'generic_error': (400, None, "Expected error"),
    'one_pk_record': (200, {
        "records": [{
            'account': dict(name='user123'),
            'owner': dict(uuid='98765'),
            'public_key': '161245ASDF',
            'index': 12,
            'comment': 'comment_123',
        }],
        'num_records': 1
    }, None),
    'two_pk_records': (200, {
        "records": [{
            'account': dict(name='user123'),
            'owner': dict(uuid='98765'),
            'public_key': '161245ASDF',
            'index': 12,
            'comment': 'comment_123',
        },
            {
            'account': dict(name='user123'),
            'owner': dict(uuid='98765'),
            'public_key': '161245ASDF',
            'index': 13,
            'comment': 'comment_123',
        }],
        'num_records': 2
    }, None)
}


# using pytest natively, without unittest.TestCase
@pytest.fixture
def patch_ansible():
    with patch.multiple(basic.AnsibleModule,
                        exit_json=exit_json,
                        fail_json=fail_json,
                        warn=warn) as mocks:
        global WARNINGS
        WARNINGS = list()
        yield mocks


def test_module_fail_when_required_args_missing(patch_ansible):
    ''' required arguments are reported as errors '''
    with pytest.raises(AnsibleFailJson) as exc:
        set_module_args(dict(hostname=''))
        my_module()
    print('Info: %s' % exc.value.args[0]['msg'])
    msg = 'missing required arguments: account'
    assert msg == exc.value.args[0]['msg']


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_get_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['index'] = 12
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is False
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_create_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 13
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['zero_record'],         # get
        SRR['empty_good'],          # create
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_create_idempotent(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'always'
    args['index'] = 12
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is False
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_create_always_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['empty_good'],          # create
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    print(WARNINGS)
    assert 'Module is not idempotent if index is not provided with state=present.' in WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_modify_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['index'] = 12
    args['comment'] = 'new_comment'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['empty_good'],          # modify
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_delete_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 12
    args['state'] = 'absent'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['empty_good'],          # delete
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_delete_idempotent(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'always'
    args['index'] = 12
    args['state'] = 'absent'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['zero_record'],         # get
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is False
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_delete_failed_N_records(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['state'] = 'absent'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['two_pk_records'],      # get
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error: index is required as more than one public_key exists for user account user123'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_delete_succeeded_N_records(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['state'] = 'absent'
    args['delete_all'] = True
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['two_pk_records'],      # get
        SRR['empty_good'],          # delete
        SRR['empty_good'],          # delete
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleExitJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_ensure_delete_succeeded_N_records_cluster(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['state'] = 'absent'
    args['delete_all'] = True
    args['vserver'] = None      # cluster scope
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['two_pk_records'],      # get
        SRR['empty_good'],          # delete
        SRR['empty_good'],          # delete
        SRR['end_of_sequence']
    ]
    with pytest.raises(AnsibleExitJson) as exc:
        uut_main()
    print('Info: %s' % exc.value.args[0])
    assert exc.value.args[0]['changed'] is True
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_extra_record(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['state'] = 'present'
    args['index'] = 14
    args['vserver'] = None      # cluster scope
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['two_pk_records'],      # get
        SRR['end_of_sequence']
    ]
    with pytest.raises(AnsibleFailJson) as exc:
        uut_main()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error in get_public_key: calling: security/authentication/publickeys: unexpected response'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_extra_arg_in_modify(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['state'] = 'present'
    args['index'] = 14
    args['vserver'] = None      # cluster scope
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['end_of_sequence']
    ]
    with pytest.raises(AnsibleFailJson) as exc:
        uut_main()
    print('Info: %s' % exc.value.args[0])
    msg = "Error: attributes not supported in modify: {'index': 14}"
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_empty_body_in_modify(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['end_of_sequence']
    ]
    current = dict(owner=dict(uuid=''), account=dict(name=''), index=0)
    modify = dict()
    my_obj = my_module()
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj.modify_public_key(current, modify)
    print('Info: %s' % exc.value.args[0])
    msg = 'Error: nothing to change - modify called with: {}'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_create_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 13
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['zero_record'],         # get
        SRR['generic_error'],       # create
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error in create_public_key: Expected error'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_delete_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 12
    args['state'] = 'absent'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['generic_error'],       # delete
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error in delete_public_key: Expected error'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_modify_called(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 12
    args['comment'] = 'change_me'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_8'],         # get version
        SRR['one_pk_record'],       # get
        SRR['generic_error'],       # modify
        SRR['end_of_sequence']
    ]
    my_obj = my_module()
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj.apply()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error in modify_public_key: Expected error'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_older_version(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'auto'
    args['index'] = 12
    args['comment'] = 'change_me'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_6'],         # get version
        SRR['end_of_sequence']
    ]
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj = my_module()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error: na_ontap_publickey only supports REST, and requires ONTAP 9.7 or later.  Found: 9.6.'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS


@patch('ansible_collections.netapp.ontap.plugins.module_utils.netapp.OntapRestAPI.send_request')
def test_negative_zapi_only(mock_request, patch_ansible):
    ''' test get'''
    args = dict(default_args())
    args['use_rest'] = 'never'
    args['index'] = 12
    args['comment'] = 'change_me'
    set_module_args(args)
    mock_request.side_effect = [
        SRR['is_rest_9_6'],         # get version
        SRR['end_of_sequence']
    ]
    with pytest.raises(AnsibleFailJson) as exc:
        my_obj = my_module()
    print('Info: %s' % exc.value.args[0])
    msg = 'Error: REST is required for this module, found: "use_rest: never"'
    assert msg in exc.value.args[0]['msg']
    assert not WARNINGS