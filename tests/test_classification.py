import unittest

from alertsrv.classification import classify_event


class ClassificationTests(unittest.TestCase):
    def test_missile_warning(self):
        self.assertEqual(classify_event("Объявлена ракетная опасность"), ("air_threat", "missile_warning"))

    def test_drone_warning(self):
        self.assertEqual(classify_event("Угроза атаки БПЛА"), ("air_threat", "drone_warning"))

    def test_high_readiness(self):
        self.assertEqual(classify_event("Введен режим повышенной готовности"), ("emergency_mode", "high_readiness"))

    def test_emergency_situation(self):
        self.assertEqual(classify_event("Введен режим чрезвычайной ситуации"), ("emergency_mode", "emergency_situation"))

    def test_emergency_regime(self):
        self.assertEqual(classify_event("Введен режим чрезвычайного положения"), ("emergency_mode", "emergency_regime"))

    def test_animal_quarantine(self):
        self.assertEqual(classify_event("Установлен карантин по бешенству животных"), ("quarantine", "animal_quarantine"))

    def test_public_health_quarantine(self):
        self.assertEqual(classify_event("Введены ограничительные мероприятия (карантин)"), ("quarantine", "public_health_quarantine"))


if __name__ == "__main__":
    unittest.main()
