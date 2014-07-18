# -*- coding: utf-8 -*-

import time
import multiprocessing

import thriftpy
thriftpy.install_import_hook()

from thriftpy.rpc import make_server, client_context

import addressbook_thrift as addressbook


class Dispatcher(object):
    def __init__(self):
        self.ab = addressbook.AddressBook()
        self.ab.people = {}

    def ping(self):
        return True

    def add(self, person):
        self.ab.people[person.name] = person
        return True

    def remove(self, name):
        try:
            self.ab.people.pop(name)
            return True
        except KeyError:
            raise addressbook.PersonNotExistsError(
                "{} not exists".format(name))

    def get(self, name):
        try:
            return self.ab.people[name]
        except KeyError:
            raise addressbook.PersonNotExistsError(
                "{} not exists".format(name))

    def book(self):
        return self.ab

    def get_phonenumbers(self, name, count):
        p = [self.ab.people[name].phones[0]] if name in self.ab.people else []
        return p * count

    def get_phones(self, name):
        phone_numbers = self.ab.people[name].phones
        return {p.type: p.number for p in phone_numbers}

    def build_thrift_meta(self, api, **kwds):
        return 'custom-meta-builder-%s' % api


def serve():
    server = make_server(addressbook.AddressBookService, Dispatcher(),
                         '127.0.0.1', 8000)
    print("serving...")
    server.serve()


def client():
    return client_context(addressbook.AddressBookService, '127.0.0.1', 8000)


def rpc_client():
    # test void request
    with client() as c:
        assert c.ping() is None

    phone1 = addressbook.PhoneNumber()
    phone1.type = addressbook.PhoneType.MOBILE
    phone1.number = '555-1212'
    phone2 = addressbook.PhoneNumber()
    phone2.type = addressbook.PhoneType.HOME
    phone2.number = '555-1234'
    person = addressbook.Person()
    person.name = "Alice"
    person.phones = [phone1, phone2]
    person.created_at = int(time.time())

    # test put struct
    with client() as c:
        assert c.add(person)

    # test get struct
    with client() as c:
        alice = c.get("Alice")
        assert person == alice

    # test get complex struct
    with client() as c:
        # test get list
        # assert isinstance(c.get_phonenumbers("Alice"), list)

        # test get empty list
        assert len(c.get_phonenumbers("Alice", 0)) == 0
        assert len(c.get_phonenumbers("Alice", 1000)) == 1000

        # assert isinstance(c.get_phones("Alice"), dict)
        # assert isinstance(c.book(), addressbook.AddressBook)

    # test exception
    with client() as c:
        try:
            name = "Bob"
            print("Try to remove non-exists name...")
            c.remove(name)
        except addressbook.PersonNotExistsError as e:
            print("remove({}) -> {}".format(name, e))

    # test meta
    with client() as c:
        c.ping()
        assert c.last_call_meta == 'custom-meta-builder-ping'


def test_rpc():
    p = multiprocessing.Process(target=serve)
    p.start()
    time.sleep(0.1)

    try:
        rpc_client()
    except:
        raise
    finally:
        p.terminate()


if __name__ == "__main__":
    test_rpc()
