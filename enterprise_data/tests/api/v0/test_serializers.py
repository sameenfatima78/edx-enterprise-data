# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` serializer module.
"""

from __future__ import absolute_import, unicode_literals

from datetime import timedelta

import ddt
from pytest import mark, raises
from rest_framework.test import APITransactionTestCase

from django.utils import timezone

from enterprise_data.api.v0.serializers import EnterpriseEnrollment, EnterpriseEnrollmentSerializer
from enterprise_data.tests.test_utils import EnterpriseUserFactory


@mark.django_db
@ddt.ddt
class TestEnterpriseEnrollmentSerializer(APITransactionTestCase):
    """
    Tests for `enterprise_enrollment` API serializer.
    """

    def setUp(self):
        super(TestEnterpriseEnrollmentSerializer, self).setUp()

        EnterpriseUserFactory(enterprise_user_id=1)
        self.enrollment_data = {
            "id": 1,
            "enterprise_id": "ee5e6b3a-069a-4947-bb8d-d2dbc323396c",
            "enterprise_name": "Enterprise 1",
            "lms_user_id": 11,
            "enterprise_user": 1,
            "course_id": "edX/Open_DemoX/edx_demo_course",
            "enrollment_created_timestamp": "2014-06-27T16:02:38Z",
            "unenrollment_timestamp": None,
            "user_current_enrollment_mode": "verified",
            "consent_granted": 1,
            "letter_grade": "Pass",
            "progress_status": "Failed",
            "passed_timestamp": "2017-05-09T16:27:34.690065Z",
            "enterprise_sso_uid": "harry",
            "course_title": "All about acceptance testing!",
            "course_start": "2016-09-01T00:00:00Z",
            "course_end": "2016-12-01T00:00:00Z",
            "course_pacing_type": "instructor_paced",
            "course_duration_weeks": "8",
            "course_min_effort": 2,
            "course_max_effort": 4,
            "user_account_creation_timestamp": "2015-02-12T23:14:35Z",
            "user_email": "test@example.com",
            "user_username": "test_user",
            "course_key": "edX/Open_DemoX",
            "enterprise_site_id": 1,
            "current_grade": 0.80,
            "discount_price": "120.00",
            "last_activity_date": "2017-06-23",
            "coupon_code": "PIPNJSUK33P7PTZH",
            "user_country_code": "US",
            "course_price": "200.00",
            "coupon_name": "Enterprise Entitlement Coupon",
            "offer": "Percentage, 100 (#1234)",
            "unenrollment_end_within_date": None,
        }

        self.course_api_url = '/enterprise/v1/enterprise-catalogs/{enterprise_id}/courses/{course_id}'.format(
            enterprise_id=self.enrollment_data['enterprise_id'], course_id=self.enrollment_data['course_id']
        )

    def test_enrollment_serialization(self):
        expected_serialized_data = dict(self.enrollment_data, course_api_url=self.course_api_url)

        serializer = EnterpriseEnrollmentSerializer(data=self.enrollment_data)
        serializer.is_valid()
        serializer.save()

        enterprise_enrollment_id = EnterpriseEnrollment.objects.first().id
        expected_serialized_data['id'] = enterprise_enrollment_id
        assert serializer.data == expected_serialized_data

    @ddt.data(
        # No course start date
        (None, '2016-12-01T00:00:00Z', '2016-12-01T00:00:00Z', True),
        # Same day enroll/un-enroll
        ('2016-12-14T00:00:00Z', '2016-12-01T00:00:00Z', '2016-12-01T01:00:00Z', True),
        # Un-enroll on next day of enrollment
        ('2016-12-14T00:00:00Z', '2016-12-01T00:00:00Z', '2016-12-02T01:00:00Z', True),
        # Un-enroll on same day as course start
        ('2016-12-14T00:00:00Z', '2016-12-01T00:00:00Z', '2016-12-14T01:00:00Z', True),
        # Un-enroll on same day as course start and enrollment
        ('2016-12-14T00:00:00Z', '2016-12-14T00:00:00Z', '2016-12-14T01:00:00Z', True),
        # Un-enroll on 14th day of course start
        ('2016-12-14T00:00:00Z', '2016-12-01T00:00:00Z', '2016-12-28T01:00:00Z', True),
        # Un-enroll on 15th day of course start
        ('2016-12-14T00:00:00Z', '2016-12-01T00:00:00Z', '2016-12-29T00:00:00Z', False),
        # Un-enroll on 14th day of enrollment
        ('2016-12-14T00:00:00Z', '2016-12-15T00:00:00Z', '2016-12-29T00:00:00Z', True),
        # Un-enroll on 15th day of enrollment
        ('2016-12-14T00:00:00Z', '2016-12-15T00:00:00Z', '2016-12-30T00:00:00Z', False),
        # Un-enroll earlier than enrollment
        ('2016-12-14T00:00:00Z', '2016-12-15T00:00:00Z', '2016-12-14T00:00:00Z', True),
    )
    @ddt.unpack
    def test_unenrollment_end_within_date(
            self, course_start, enrollment_created_timestamp, unenrollment_timestamp,
            expected_unenrollment_end_within_date
    ):
        self.enrollment_data['course_start'] = course_start
        self.enrollment_data['unenrollment_timestamp'] = unenrollment_timestamp
        self.enrollment_data['enrollment_created_timestamp'] = enrollment_created_timestamp

        serializer = EnterpriseEnrollmentSerializer(data=self.enrollment_data)
        serializer.is_valid()
        serializer.save()
        self.assertEqual(expected_unenrollment_end_within_date, serializer.data['unenrollment_end_within_date'])

    @ddt.data(
        # No course end date and has_passed is False
        (None, False, 'In Progress'),
        # No course end date and has_passed is True
        (None, True, 'Passed'),
        # Course not ended and has_passed is False
        (timezone.now() + timedelta(days=1), False, 'In Progress'),
        # Course about to end today and has_passed is False
        (timezone.now(), False, 'In Progress'),
        # Course already ended and has_passed is False
        (timezone.now() + timedelta(days=-1), False, 'Failed'),
        # Course already ended and has_passed is True
        (timezone.now() + timedelta(days=-1), True, 'Passed'),
        # Course not ended and has_passed is True
        (timezone.now() + timedelta(days=1), True, 'Passed'),
    )
    @ddt.unpack
    def test_progress_status(self, course_end, has_passed, expected_progress_status):
        self.enrollment_data['course_end'] = course_end
        self.enrollment_data['has_passed'] = has_passed

        serializer = EnterpriseEnrollmentSerializer(data=self.enrollment_data)
        serializer.is_valid()
        serializer.save()
        self.assertEqual(expected_progress_status, serializer.data['progress_status'])
