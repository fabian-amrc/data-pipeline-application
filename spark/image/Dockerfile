FROM bitnamilegacy/spark:3.5.3

ENV JAVA_HOME=/opt/bitnami/java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates dos2unix python3-pip \
  && rm -rf /var/lib/apt/lists/*

COPY certs/ /tmp/spark-certs/

RUN if [ -f /tmp/spark-certs/minikubeCA.crt ]; then \
    dos2unix /tmp/spark-certs/minikubeCA.crt; \
    keytool -importcert -noprompt \
      -alias minio-ca \
      -file /tmp/spark-certs/minikubeCA.crt \
      -keystore "${JAVA_HOME}/lib/security/cacerts" \
      -storepass changeit; \
  fi \
  && rm -rf /tmp/spark-certs

WORKDIR /app

RUN pip install --no-cache-dir pyspark==3.5.3

# Delta Lake jars
ADD https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.3.0/delta-spark_2.12-3.3.0.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/io/delta/delta-standalone_2.12/3.3.0/delta-standalone_2.12-3.3.0.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/io/delta/delta-storage/3.3.0/delta-storage-3.3.0.jar /opt/bitnami/spark/jars/

# Unity Catalog jars
ADD https://repo1.maven.org/maven2/io/unitycatalog/unitycatalog-spark_2.12/0.2.1/unitycatalog-spark_2.12-0.2.1.jar /opt/bitnami/spark/jars/

# Kafka jars
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.2/kafka-clients-2.8.2.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10-assembly_2.12/3.5.3/spark-streaming-kafka-0-10-assembly_2.12-3.5.3.jar /opt/bitnami/spark/jars/
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar /opt/bitnami/spark/jars/

# Apache jars
ADD https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.12.1/commons-pool2-2.12.1.jar /opt/bitnami/spark/jars/

COPY conf/spark-defaults.conf /opt/bitnami/spark/conf/spark-defaults.conf

RUN chmod -R a+r /opt/bitnami/spark/jars /opt/bitnami/spark/conf/spark-defaults.conf

USER 1001
