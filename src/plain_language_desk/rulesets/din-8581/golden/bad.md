# Allgemeines

Es ist darauf hinzuweisen, dass die Durchführung der Einsatzprüfung
grundsätzlich vor der Veröffentlichung der Ankündigung zu erfolgen hat, um
sicherzustellen, dass die Bereitstellung der Veröffentlichung im Cluster
tatsächlich erfolgreich abgeschlossen worden ist und somit keine
unvorhergesehenen Abweichungen zwischen dem gespeicherten Image-Digest und
demjenigen Digest, welcher im Cluster tatsächlich zur Anwendung kommt,
bestehen, da andernfalls die Gefahr bestehen würde, dass eine Ankündigung
erfolgt, die der tatsächlichen Lage nicht entspricht.

Es wird ein Vergleich des gespeicherten Image-Digests mit dem im Cluster
laufenden Digest durchgeführt; dieser Vergleich wird durch den
Einsatzcheck ermöglicht, der die Applikation zur Prüfung der Deployments
zur Verfügung stellt und somit die Utilisierung von Prüfprozessen im
Hinblick auf die Deployment-Verifikation in der Lage ist deutlich zu
vereinfachen, wobei etwaige Abweichungen z. B. durch 3 erneute Versuche
im Abstand von jeweils 5 Minuten ermittelt werden können, und sollten
dabei Differenzen festgestellt werden, würden entsprechende Maßnahmen
durch die für die Verifikation zuständige Person eingeleitet, wobei die
Ankündigung bis zur vollständigen Klärung der Situation nicht erfolgen
darf und die zuständigen Stellen zu informieren sind.
