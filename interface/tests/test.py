# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest
import time


class Test(unittest.TestCase):
    def setUp(self):
        #self.driver = webdriver.Chrome()
        from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
        binary = FirefoxBinary('/gel/usr/yahog/browser/firefox/firefox')
        self.driver = webdriver.Firefox(firefox_binary=binary)
        self.driver.implicitly_wait(30)
        #self.base_url = "http://127.0.0.1:8000/"
        #self.base_url = "http://gif1001-sim.gel.ulaval.ca/?sim=nouveau#tabsmain-simulation"
        self.base_url = "http://gif1001-sim.gel.ulaval.ca/?page=tp&sim=debug#tabsmain-simulation"
        self.verificationErrors = []
        self.accept_next_alert = True

    def test_(self):
        wdw = WebDriverWait(self.driver, 100)
        driver = self.driver
        driver.get(self.base_url)
        time.sleep(3)
        driver.find_element_by_id("assemble").click()
        #driver.find_element_by_id("configurations").click()
        #driver.find_element_by_id("animate_speed").clear()
        #driver.find_element_by_id("animate_speed").send_keys("0")
        #driver.find_element_by_class_name("ui-icon-closethick").click()
        time.sleep(2)
        wdw.until(EC.element_to_be_clickable((By.ID, "run")))
        driver.find_element_by_id("run").click()
        time.sleep(60*5)
        driver.find_element_by_id("run").click()

    def is_element_present(self, how, what):
        try: self.driver.find_element(by=how, value=what)
        except NoSuchElementException as e: return False
        return True

    def is_alert_present(self):
        try: self.driver.switch_to_alert()
        except NoAlertPresentException as e: return False
        return True

    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally: self.accept_next_alert = True

    def tearDown(self):
        self.driver.quit()
        self.assertEqual([], self.verificationErrors)


if __name__ == "__main__":
    unittest.main()
