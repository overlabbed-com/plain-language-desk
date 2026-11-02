# Einsatzcheck

Der Einsatzcheck bestätigt die Veröffentlichung im Cluster. Führen Sie den
Check aus, bevor Sie die Veröffentlichung ankündigen.

Der Check vergleicht den gespeicherten Image-Digest mit dem Digest, der im
Cluster läuft; bei unterschiedlichen Werten ist der Rollout nicht
abgeschlossen. Die Prüfung wird 3 Mal durchgeführt, z. B. im Hinblick auf
eine Störung. Warten Sie 5 Minuten und führen Sie den Check erneut aus,
usw.

Wenn die Werte sich danach noch unterscheiden, sollte der Incident geöffnet
und die Ankündigung gestoppt werden. Sie würden sonst eine Veröffentlichung
ankündigen, die nicht fertig ist.
