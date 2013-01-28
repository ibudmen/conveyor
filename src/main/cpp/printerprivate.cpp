// vim:cindent:cino=\:0:et:fenc=utf-8:ff=unix:sw=4:ts=4:

#include <conveyor/conveyor.h>

#include "printerprivate.h"

#include "conveyorprivate.h"

#include <stdexcept>

#include <QString>
#include <QStringList>

namespace conveyor
{
    PrinterPrivate::PrinterPrivate
        ( Conveyor * const conveyor
        , Printer * const printer
        , QString const & uniqueName
        )
        : m_conveyor (conveyor)
        , m_printer (printer)
        , m_uniqueName (uniqueName)
    {
        this->m_canPrint = true;
        this->m_canPrintToFile = true;
        this->m_displayName = "Dummy Printer";
        this->m_printerType = "Replicator";
        this->m_machineNames = QStringList("TheReplicator");
        this->m_numberOfToolheads = 2;
        this->m_hasHeatedPlatform = true;
    }

    void
    PrinterPrivate::updateFromJson(Json::Value const & json)
    {
        QString const uniqueName(json["uniqueName"].asCString());
        QString const displayName(json["displayName"].asCString());
        bool const canPrint(json["canPrint"].asBool());
        bool const canPrintToFile(json["canPrintToFile"].asBool());
        QString const printerType(QString(json["printerType"].asCString()));
        int const numberOfToolheads(json["numberOfToolheads"].asInt());
        bool const hasHeatedPlatform(json["hasHeatedPlatform"].asBool());
        QStringList machineNames;
        for(Json::ArrayIndex i = 0; i < json["machineNames"].size(); ++i)
        {
            machineNames << QString(json["machineNames"][i].asCString());
        }

        float buildVolumeXmin, buildVolumeYmin, buildVolumeZmin,
              buildVolumeXmax, buildVolumeYmax, buildVolumeZmax;

        if ("The Replicator Single" == printerType) {
            buildVolumeXmin = -113.5;
            buildVolumeYmin = -74;
            buildVolumeZmin = 0;
            buildVolumeXmax = 113.5;
            buildVolumeYmax = 74;
            buildVolumeZmax = 150;
        } else if ("The Replicator Dual" == printerType) {
            buildVolumeXmin = -113.5;
            buildVolumeYmin = -74;
            buildVolumeZmin = 0;
            buildVolumeXmax = 113.5;
            buildVolumeYmax = 74;
            buildVolumeZmax = 150;
        } else if ("The Replicator 2" == printerType) {
            buildVolumeXmin = -142.5;
            buildVolumeYmin = -75;
            buildVolumeZmin = 0;
            buildVolumeXmax = 142.5;
            buildVolumeYmax = 75;
            buildVolumeZmax = 150;
        } else if ("The Replicator 2X" == printerType) {
            // TODO(nicholasbishop): these values are the same as rep2
            // for now, not sure if correct though
            buildVolumeXmin = -142.5;
            buildVolumeYmin = -75;
            buildVolumeZmin = 0;
            buildVolumeXmax = 142.5;
            buildVolumeYmax = 75;
            buildVolumeZmax = 150;
        } else {
            // Let's use TOM as default
            const int xlen = 106;
            const int ylen = 120;
            const int zlen = 106;
            buildVolumeXmin = -xlen / 2;
            buildVolumeYmin = -ylen / 2;
            buildVolumeZmin = 0;
            buildVolumeXmax = xlen / 2;
            buildVolumeYmax = ylen / 2;
            buildVolumeZmax = zlen;
        }

        m_uniqueName = uniqueName;
        m_displayName = displayName;
        m_machineNames = machineNames;
        m_canPrint = canPrint;
        m_canPrintToFile = canPrintToFile;
        m_printerType = printerType;
        m_numberOfToolheads = numberOfToolheads;
        m_hasHeatedPlatform = hasHeatedPlatform;
        m_buildVolumeXmin = buildVolumeXmin;
        m_buildVolumeYmin = buildVolumeYmin;
        m_buildVolumeZmin = buildVolumeZmin;
        m_buildVolumeXmax = buildVolumeXmax;
        m_buildVolumeYmax = buildVolumeYmax;
        m_buildVolumeZmax = buildVolumeZmax;

        // Get firmware version
        const std::string firmwareVersionKey("firmware_version");
        if (json.isMember(firmwareVersionKey)) {
          if (json[firmwareVersionKey].isInt()) {
            const int combinedVersion(json[firmwareVersionKey].asInt());
            if (combinedVersion < 100) {
              // At least a three digit number is expected
              m_firmwareVersion.m_error = kFirmwareVersionTooSmall;
            } else {
              m_firmwareVersion.m_major = combinedVersion / 100;
              m_firmwareVersion.m_minor = (combinedVersion
                                           - m_firmwareVersion.m_major * 100);
              m_firmwareVersion.m_error = kFirmwareVersionOK;
            }
          } else {
            m_firmwareVersion.m_error = kFirmwareVersionNotInteger;
          }
        }
        
        // Temperature of extruder(s) and platform(s)
        if (json.isMember("temperature")) {
            const Json::Value &temperature(json["temperature"]);
            if (temperature.isMember("tools")) {
                ToolTemperature::updateFromJson(m_toolTemperature.tools,
                                                temperature["tools"]);
            }
            if (temperature.isMember("heated_platforms")) {
                ToolTemperature::updateFromJson(m_toolTemperature.heated_platforms,
                                                temperature["heated_platforms"]);
            }
        }
    }

    Job *
    PrinterPrivate::print (QString const & inputFile
                           , const SlicerConfiguration & slicer_conf
                           , QString const & material
                           , bool const skipStartEnd)
    {
        Job * const result
            ( this->m_conveyor->m_private->print
                ( this->m_printer
                , inputFile
                , slicer_conf
                , material
                , skipStartEnd
                )
            );
        return result;
    }

    Job *
    PrinterPrivate::printToFile
        ( QString const & inputFile
        , QString const & outputFile
        , const SlicerConfiguration & slicer_conf
        , QString const & material
        , bool const skipStartEnd
        , QString const & printToFileType
        )
    {
        Job * const result
            ( this->m_conveyor->m_private->printToFile
                ( this->m_printer
                , inputFile
                , outputFile
                , slicer_conf
                , material
                , skipStartEnd
                , printToFileType
                )
            );
        return result;
    }

    Job *
    PrinterPrivate::slice
        ( QString const & inputFile
        , QString const & outputFile
        , const SlicerConfiguration & slicer_conf
        , QString const & material
        , bool const withStartEnd
        )
    {
        Job * const result
            ( this->m_conveyor->m_private->slice
                ( this->m_printer
                , inputFile
                , outputFile
                , slicer_conf
                , material
                , withStartEnd
                )
            );
        return result;
    }
}
