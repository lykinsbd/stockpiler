import base64
import os


from pyfakefs import fake_filesystem_unittest


from stockpiler.__main__ import gather_credentials


class TestGatherCredentials(fake_filesystem_unittest.TestCase):
    def __init__(self, *args, **kwargs):
        """
        Setup our object for this test case
        :param args:
        :param kwargs:
        """

        super().__init__(*args, **kwargs)

        # Credentials:
        self.credential_dict = {
            "STOCKPILER_USER": "test_user",
            "STOCKPILER_PW": "test_pw",
            "STOCKPILER_ENABLE": "test_en",
        }
        self.credential_full_tuple = ("test_user", "test_pw", "test_en")
        self.credential_partial_tuple = ("test_user", "test_pw", "test_pw")

        # Generate the credential strings for putting into fake file-like IO objects.
        self.full_credential_string = ""
        for k, v in self.credential_dict.items():
            self.full_credential_string += f"{k}:{v}\n"
        self.non_b64_credential_string = self.full_credential_string
        self.full_credential_string = base64.b64encode(self.full_credential_string.encode()).decode()

        self.partial_credential_string = ""
        for k, v in self.credential_dict.items():
            if k != "STOCKPILER_ENABLE":
                self.partial_credential_string += f"{k}:{v}\n"
        self.partial_credential_string = base64.b64encode(self.partial_credential_string.encode()).decode()

        # Credential File Path
        self.file_path = "/opt/stockpiler/.stockpiler.b64"

        # Environment
        self.good_environ = None
        self.bad_environ = None
        self.partial_environ = None

    def setUp(self) -> None:
        """
        Plumb up our environment and file like objects
        :return:
        """

        # Setup our fake file system
        self.setUpPyfakefs()

        # Environment
        self.original_environ = os.environ.copy()
        self.good_environ = os.environ.copy()
        for k, v in self.credential_dict.items():
            self.good_environ[k] = v
        self.bad_environ = os.environ.copy()
        self.partial_environ = self.good_environ.copy()
        self.partial_environ.pop("STOCKPILER_ENABLE")

    def test_environment_credentials(self):
        """
        Tests for environment variable configured credentials
        :return:
        """

        # Test correct environment configuration
        with self.subTest(msg="Checking correct environment based credentials..."):
            os.environ = self.good_environ
            self.assertEqual(gather_credentials(), self.credential_full_tuple)

        # Test Partial environment configuration (no enable set in ENV variable)
        with self.subTest(msg="Checking partial environment based credentials..."):
            os.environ = self.partial_environ
            self.assertEqual(gather_credentials(), self.credential_partial_tuple)

        # Test No environment variable
        with self.subTest(msg="Checking missing environment based credentials..."):
            os.environ = self.original_environ
            with self.assertRaises(expected_exception=OSError):
                gather_credentials()

    def test_credential_file(self):
        """
        Tests for credential file configured credentials
        :return:
        """

        # Test Correct configuration file
        with self.subTest(msg="Checking correct file based credentials..."):
            # Create credential file in filesystem
            self.fs.create_file(file_path=self.file_path, contents=self.full_credential_string, st_mode=0o100600)
            # Test it
            self.assertEqual(
                gather_credentials(credential_file=self.file_path), self.credential_full_tuple
            )

        # Test Partial configuration file
        with self.subTest(msg="Checking partial credential file..."):
            # Delete our fake file for the next test
            self.fs.remove_object(file_path=self.file_path)
            self.fs.create_file(file_path=self.file_path, contents=self.partial_credential_string, st_mode=0o100600)
            self.assertEqual(
                gather_credentials(credential_file=self.file_path), self.credential_partial_tuple
            )

        # Test existing, but empty credential file
        with self.subTest(msg="Checking empty credential file..."):
            self.fs.remove_object(file_path=self.file_path)
            self.fs.create_file(file_path=self.file_path, contents="", st_mode=0o100600)
            with self.assertRaises(expected_exception=OSError):
                gather_credentials(credential_file=self.file_path)

        # Test existing credential file but not b64 encoded contents
        with self.subTest(msg="Checking non-Base64 encoded credential file..."):
            self.fs.remove_object(file_path=self.file_path)
            self.fs.create_file(file_path=self.file_path, contents=self.non_b64_credential_string, st_mode=0o100600)
            with self.assertRaises(expected_exception=OSError):
                gather_credentials(credential_file=self.file_path)

        # Test over permissive permissions on credential file
        with self.subTest(msg="Checking overly permissive premissions on credential file..."):
            self.fs.remove_object(file_path=self.file_path)
            self.fs.create_file(file_path=self.file_path, contents=self.full_credential_string)
            with self.assertRaises(expected_exception=OSError):
                gather_credentials(credential_file=self.file_path)

        # Test non-existing credential file
        with self.subTest(msg="Checkin non-existnat credential file..."):
            with self.assertRaises(expected_exception=OSError):
                gather_credentials(credential_file=self.file_path)
